"""Telemetría de cada web: recoger los datos (sin IA) y tenerlos en una base consultable para decidir.

  clientes/<web>/datos/<fuente>/…   las fotos que dejan las herramientas (gsc, enlaces, bots, ia, competencia…)
  clientes/<web>/datos/metricas.db  SQLite con las series de Search Console (por día, consulta×página y página)

  hseo_datos.py recoger <web>             lanza las herramientas que su configuración permite y actualiza la base
  hseo_datos.py actualizar <web>          solo carga en la base las fotos que haya
  hseo_datos.py resumen <web> [--dias 28] últimos N días frente a los N anteriores, y consultas en posiciones 8-20
  hseo_datos.py comparar <web> <cambio>   antes y después de un cambio de cambios.jsonl (28 días)

`recoger` solo imprime si algo falla (el cron lo entrega tal cual; una salida vacía no avisa a nadie).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sqlite3
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _cargar(nombre: str):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, AQUI / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


B = _cargar("hseo_base")
C = _cargar("hseo_clientes")
PL = _cargar("hseo_pipelines")
Rechazo = B.Rechazo


def _num(fila: dict, *claves) -> float:
    for k in claves:
        if fila.get(k) is not None:
            try:
                return float(fila[k])
            except (TypeError, ValueError):
                pass
    return 0.0


def _db(slug: str) -> sqlite3.Connection:
    f = C.carpeta(slug) / "datos" / "metricas.db"
    f.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(f)
    con.executescript("""
      CREATE TABLE IF NOT EXISTS gsc_dia (fecha TEXT PRIMARY KEY, clics REAL, impresiones REAL, ctr REAL, posicion REAL);
      CREATE TABLE IF NOT EXISTS gsc_consulta (fecha TEXT, consulta TEXT, pagina TEXT, clics REAL, impresiones REAL,
        ctr REAL, posicion REAL, PRIMARY KEY (fecha, consulta, pagina));
      CREATE TABLE IF NOT EXISTS gsc_pagina (fecha TEXT, pagina TEXT, clics REAL, impresiones REAL, ctr REAL,
        posicion REAL, PRIMARY KEY (fecha, pagina));
    """)
    return con


def actualizar(slug: str) -> int:
    """Carga en metricas.db las fotos diarias de Search Console (idempotente). Devuelve cuántos días cargó."""
    d = C.carpeta(slug) / "datos" / "gsc"
    if not d.is_dir():
        return 0
    con = _db(slug)
    n = 0
    with con:
        for f in sorted(d.glob("????-??-??.json")):
            datos = B.leer(f) or {}
            fecha = f.stem
            t = datos.get("totales") or {}
            con.execute("INSERT OR REPLACE INTO gsc_dia VALUES (?,?,?,?,?)", (fecha, _num(t, "clics", "clicks"),
                        _num(t, "impresiones", "impressions"), _num(t, "ctr"), _num(t, "posicion", "position")))
            con.execute("DELETE FROM gsc_consulta WHERE fecha = ?", (fecha,))
            for r in datos.get("consulta_pagina") or []:
                con.execute("INSERT OR REPLACE INTO gsc_consulta VALUES (?,?,?,?,?,?,?)", (
                    fecha, r.get("query") or r.get("consulta") or "", r.get("page") or r.get("pagina") or "",
                    _num(r, "clics", "clicks"), _num(r, "impresiones", "impressions"), _num(r, "ctr"),
                    _num(r, "posicion", "position")))
            con.execute("DELETE FROM gsc_pagina WHERE fecha = ?", (fecha,))
            for r in datos.get("pagina") or []:
                con.execute("INSERT OR REPLACE INTO gsc_pagina VALUES (?,?,?,?,?,?)", (
                    fecha, r.get("page") or r.get("pagina") or "", _num(r, "clics", "clicks"),
                    _num(r, "impresiones", "impressions"), _num(r, "ctr"), _num(r, "posicion", "position")))
            n += 1
    con.close()
    return n


def _herramienta(nombre: str, slug: str, *args: str, timeout: int = 900) -> str:
    """Ejecuta una herramienta; devuelve "" si fue bien o el motivo si falló (sin claves: las herramientas las tapan)."""
    exe = PL.raiz() / "herramientas" / nombre
    if not exe.exists():
        return f"{nombre}: no está instalada"
    try:
        r = subprocess.run([sys.executable, str(exe), "--cliente", slug, *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return f"{nombre}: tardó más de {timeout // 60} min"
    if r.returncode != 0:
        return f"{nombre}: {(r.stderr or r.stdout).strip().splitlines()[-1][:200] if (r.stderr or r.stdout).strip() else f'salió con {r.returncode}'}"
    return ""


def recoger(slug: str, hoy: date | None = None) -> list:
    cfg = C.leer(slug)
    if (cfg.get("politicas") or {}).get("pausado"):
        return []
    caps = C.capacidades(cfg)
    hoy = hoy or datetime.now(timezone.utc).date()
    fallos = []
    if "gsc" in caps:
        fallos.append(_herramienta("guardar-gsc", slug))
    if hoy.weekday() == 0:   # los lunes: enlaces y bots (fotos semanales)
        if "bing" in caps:
            fallos.append(_herramienta("enlaces-bing", slug))
        if "analitica:cloudflare" in caps:
            fallos.append(_herramienta("bots-ia", slug, "--dias", "7"))
    actualizar(slug)
    B.anotar(C.carpeta(slug) / "datos" / "recogidas.jsonl", {"ts": B.ahora(), "fallos": [f for f in fallos if f]})
    return [f for f in fallos if f]


def _suma(con, desde: str, hasta: str, pagina: str | None = None) -> dict:
    if pagina:
        r = con.execute("SELECT COALESCE(SUM(clics),0), COALESCE(SUM(impresiones),0), AVG(posicion), COUNT(DISTINCT fecha) "
                        "FROM gsc_pagina WHERE fecha BETWEEN ? AND ? AND rtrim(pagina,'/') = rtrim(?,'/')",
                        (desde, hasta, pagina)).fetchone()
    else:
        r = con.execute("SELECT COALESCE(SUM(clics),0), COALESCE(SUM(impresiones),0), AVG(posicion), COUNT(*) "
                        "FROM gsc_dia WHERE fecha BETWEEN ? AND ?", (desde, hasta)).fetchone()
    clics, imp, pos, dias = r
    return {"clics": int(clics), "impresiones": int(imp), "ctr": round(clics / imp * 100, 2) if imp else 0.0,
            "posicion": round(pos, 1) if pos else None, "dias": dias}


def _ultimo(con) -> date | None:
    r = con.execute("SELECT MAX(fecha) FROM gsc_dia").fetchone()[0]
    return date.fromisoformat(r) if r else None


def resumen(slug: str, dias: int = 28) -> dict:
    con = _db(slug)
    fin = _ultimo(con)
    if not fin:
        con.close()
        return {"hay_datos": False}
    ini = fin - timedelta(days=dias - 1)
    ahora_ = _suma(con, ini.isoformat(), fin.isoformat())
    antes = _suma(con, (ini - timedelta(days=dias)).isoformat(), (ini - timedelta(days=1)).isoformat())
    serie = [{"fecha": f, "clics": int(c), "impresiones": int(i)} for f, c, i in con.execute(
        "SELECT fecha, clics, impresiones FROM gsc_dia WHERE fecha >= ? ORDER BY fecha", ((fin - timedelta(days=89)).isoformat(),))]
    cerca = [{"consulta": q, "pagina": p, "impresiones": int(i), "clics": int(c), "posicion": round(pos, 1)} for q, p, i, c, pos in con.execute(
        "SELECT consulta, pagina, SUM(impresiones) i, SUM(clics), AVG(posicion) pos FROM gsc_consulta "
        "WHERE fecha BETWEEN ? AND ? GROUP BY consulta, pagina HAVING pos BETWEEN 8 AND 20 ORDER BY i DESC LIMIT 15",
        (ini.isoformat(), fin.isoformat()))]
    con.close()
    return {"hay_datos": True, "hasta": fin.isoformat(), "dias": dias, "actual": ahora_, "anterior": antes,
            "serie": serie, "pagina_dos": cerca}


def comparar(slug: str, cambio_id: str, dias: int = 28) -> dict:
    """Antes/después de un cambio publicado: sus URL y el conjunto de la web (para descontar la tendencia)."""
    cambio = None
    try:
        for l in (C.carpeta(slug) / "cambios.jsonl").read_text().splitlines():
            r = json.loads(l)
            if r.get("id") == cambio_id or r.get("encargo") == cambio_id:
                cambio = r
    except OSError:
        pass
    if not cambio:
        raise Rechazo(f"No encuentro el cambio {cambio_id} en cambios.jsonl")
    dia = date.fromisoformat(cambio["ts"][:10])
    con = _db(slug)
    ultimo = _ultimo(con)
    if not ultimo or (ultimo - dia).days < dias:
        con.close()
        return {"cambio": cambio, "listo": False,
                "motivo": f"Aún no hay {dias} días de datos después del cambio (hay {max(0, (ultimo - dia).days) if ultimo else 0})"}
    a = ((dia - timedelta(days=dias)).isoformat(), (dia - timedelta(days=1)).isoformat())
    d = ((dia + timedelta(days=1)).isoformat(), (dia + timedelta(days=dias)).isoformat())
    urls = [u for u in ([cambio.get("url")] + (cambio.get("urls") or [])) if u]
    out = {"cambio": cambio, "listo": True, "web": {"antes": _suma(con, *a), "despues": _suma(con, *d)},
           "urls": {u: {"antes": _suma(con, *a, pagina=u), "despues": _suma(con, *d, pagina=u)} for u in urls}}
    con.close()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hseo_datos.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for n in ("recoger", "actualizar"):
        sub.add_parser(n).add_argument("web")
    r = sub.add_parser("resumen"); r.add_argument("web"); r.add_argument("--dias", type=int, default=28)
    c = sub.add_parser("comparar"); c.add_argument("web"); c.add_argument("cambio")
    x = ap.parse_args(argv)
    try:
        if x.cmd == "recoger":
            fallos = recoger(x.web)
            if fallos:
                print(f"⚠️ No se pudieron recoger todos los datos de {x.web}:\n" + "\n".join(f"- {f}" for f in fallos))
        elif x.cmd == "actualizar":
            print(f"{actualizar(x.web)} días cargados")
        elif x.cmd == "resumen":
            print(json.dumps(resumen(x.web, x.dias), ensure_ascii=False, indent=1))
        elif x.cmd == "comparar":
            print(json.dumps(comparar(x.web, x.cambio), ensure_ascii=False, indent=1))
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
