"""El cuaderno del método (la memoria GLOBAL de hermes-seo): cómo funciona el sistema, no qué pasa en cada web. Sin
modelo, una vez por semana (lunes 07:00, cron de la coordinadora). Solo método y contadores: nunca textos ni datos
privados de una web (de cada web, solo su nombre corto y sus cifras de funcionamiento).

  semana-<AAAA-Www>.md (queries/)   fallos por etapa, tasa de «la verificación pidió cambios», puertas por tipo y verbo y
                                    lo que se tarda en decidir, incidencias (y cuántas se arreglaron solas), correos
                                    enviados por tipo, coste por perfil (de los state.db de Hermes, solo lectura)
  metodo-cifras.md (concepts/)      la tabla de las últimas 12 semanas

Lo lee el coordinador para proponer mejoras del propio sistema (y la revisión mensual de novedades).

  hseo_cuaderno.py apuntar [--dias 7]
"""
from __future__ import annotations

import glob
import importlib.util
import json
import os
import sqlite3
import statistics
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import date
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
ES = _cargar("hseo_estado")


def costes(dias: int = 7, hh: Path | None = None) -> dict:
    """Coste estimado por perfil y fuente (sesiones de los state.db de Hermes, en solo lectura)."""
    hh = hh or Path(os.environ.get("HERMES_HOME_BASE") or Path.home() / ".hermes")
    desde = time.time() - dias * 86400
    out: dict = {}
    for f in [hh / "state.db"] + [Path(p) for p in glob.glob(str(hh / "profiles" / "*" / "state.db"))]:
        perfil = "default" if f.parent == hh else f.parent.name
        try:
            con = sqlite3.connect(f"file:{f}?mode=ro", uri=True, timeout=5)
            for fuente, n, usd in con.execute("SELECT source, COUNT(*), COALESCE(SUM(estimated_cost_usd),0) FROM sessions "
                                               "WHERE started_at > ? GROUP BY source", (desde,)):
                if n:
                    out.setdefault(perfil, {})[fuente or "?"] = {"sesiones": n, "usd": round(usd, 2)}
            con.close()
        except sqlite3.Error:
            continue
    return out


def cifras(dias: int = 7) -> dict:
    desde = time.time() - dias * 86400
    etapas, cambios_verif, puertas, verbos, decidir_s, incid, resueltas_solas, webs = (
        defaultdict(lambda: {"n": 0, "fallos": 0, "min": [], "usd": 0.0}), Counter(), Counter(), Counter(), [], Counter(), 0, {})
    verif_n = 0
    for slug in C.listar():
        d = C.carpeta(slug)
        w = {"etapas": 0, "usd": 0.0}
        for r in ES._jsonl(d / "etapas.jsonl"):
            if ES._ts(r.get("ts")) < desde:
                continue
            k = f"{r.get('pipeline')}/{r.get('etapa')}"
            e = etapas[k]
            e["n"] += 1; e["fallos"] += r.get("resultado") not in ("done", "cambios"); e["min"].append(float(r.get("minutos") or 0))
            e["usd"] += float(r.get("coste_usd") or 0)
            w["etapas"] += 1; w["usd"] += float(r.get("coste_usd") or 0)
            if r.get("etapa") == "verificar":
                verif_n += 1
                cambios_verif["cambios"] += r.get("resultado") == "cambios"
        for r in ES._jsonl(d / "puertas.jsonl"):
            if ES._ts(r.get("ts")) < desde:
                continue
            puertas[r.get("tipo")] += 1; verbos[f"{r.get('tipo')}:{r.get('verbo')}"] += 1
            if r.get("segundos_hasta_decidir"):
                decidir_s.append(int(r["segundos_hasta_decidir"]))
        for f in (d / "incidencias").glob("*.json") if (d / "incidencias").is_dir() else []:
            i = B.leer(f) or {}
            if ES._ts(i.get("creada")) >= desde:
                incid[i.get("clase", "?")] += 1
                resueltas_solas += bool(i.get("sola"))
        w["usd"] = round(w["usd"], 2)
        webs[slug] = w
    correos = Counter()
    for r in ES._jsonl(B.home() / "correo" / "enviados.jsonl"):
        if ES._ts(r.get("ts")) >= desde:
            correos[r.get("tipo") or "?"] += 1
    tabla = {k: {"n": v["n"], "fallos_pct": round(v["fallos"] / v["n"] * 100) if v["n"] else 0,
                 "min_medio": round(statistics.mean(v["min"]), 1) if v["min"] else 0, "usd": round(v["usd"], 2)}
             for k, v in sorted(etapas.items())}
    return {"desde": date.fromtimestamp(desde).isoformat(), "hasta": date.today().isoformat(), "etapas": tabla,
            "verificacion_pide_cambios_pct": round(cambios_verif["cambios"] / verif_n * 100) if verif_n else None,
            "puertas": dict(puertas), "verbos": dict(verbos),
            "decidir_mediana_h": round(statistics.median(decidir_s) / 3600, 1) if decidir_s else None,
            "incidencias": dict(incid), "resueltas_solas": resueltas_solas, "correos": dict(correos),
            "webs": webs, "costes_por_perfil": costes(dias)}


def _md(c: dict) -> str:
    l = [f"Del {c['desde']} al {c['hasta']}. Solo método y contadores (sin textos de ninguna web).", "", "## Etapas",
         "| pipeline/etapa | veces | fallos | min | $ |", "|---|---|---|---|---|"]
    l += [f"| {k} | {v['n']} | {v['fallos_pct']} % | {v['min_medio']} | {v['usd']} |" for k, v in c["etapas"].items()] or ["| — | 0 | | | |"]
    l += ["", f"- La verificación pidió cambios: {c['verificacion_pide_cambios_pct'] if c['verificacion_pide_cambios_pct'] is not None else '—'} %",
          f"- Puertas: {json.dumps(c['puertas'], ensure_ascii=False)} · decisiones: {json.dumps(c['verbos'], ensure_ascii=False)}",
          f"- Tiempo hasta decidir (mediana): {c['decidir_mediana_h'] if c['decidir_mediana_h'] is not None else '—'} h",
          f"- Incidencias: {json.dumps(c['incidencias'], ensure_ascii=False)} · arregladas solas: {c['resueltas_solas']}",
          f"- Correos enviados: {json.dumps(c['correos'], ensure_ascii=False)}",
          "", "## Coste por web (etapas)"]
    l += [f"- {w}: {v['etapas']} etapas, {v['usd']} $" for w, v in c["webs"].items()]
    l += ["", "## Coste por perfil (sesiones de Hermes, estimado)"]
    for perfil, fuentes in sorted(c["costes_por_perfil"].items()):
        l.append(f"- {perfil}: " + ", ".join(f"{f} {v['sesiones']} ses. {v['usd']} $" for f, v in fuentes.items()))
    return "\n".join(l)


def apuntar(dias: int = 7) -> Path:
    c = cifras(dias)
    w = B.home() / "wiki"
    sem = date.today().isocalendar()
    nombre = f"semana-{sem[0]}-W{sem[1]:02d}"
    f = w / "queries" / f"{nombre}.md"
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(f"---\ntitle: Cuaderno del método, semana {sem[1]} de {sem[0]}\ncreated: {date.today()}\nupdated: {date.today()}\n"
                 f"type: query\ntags: [resultado]\nsources: [etapas.jsonl, puertas.jsonl, incidencias, state.db]\nconfidence: high\n---\n\n"
                 f"# Cuaderno del método · semana {sem[1]}\n\n{_md(c)}\n")
    B.escribir(w / "queries" / f"{nombre}.json", c)
    filas = []
    for j in sorted((w / "queries").glob("semana-*.json"))[-12:]:
        x = B.leer(j) or {}
        usd = round(sum(v["usd"] for v in (x.get("webs") or {}).values()), 2)
        filas.append(f"| {j.stem[7:]} | {sum(v['n'] for v in (x.get('etapas') or {}).values())} | "
                     f"{x.get('verificacion_pide_cambios_pct') if x.get('verificacion_pide_cambios_pct') is not None else '—'} % | "
                     f"{sum((x.get('puertas') or {}).values())} | {x.get('decidir_mediana_h') or '—'} | "
                     f"{sum((x.get('incidencias') or {}).values())} ({x.get('resueltas_solas', 0)} solas) | {usd} |")
    (w / "concepts").mkdir(parents=True, exist_ok=True)
    (w / "concepts" / "metodo-cifras.md").write_text(
        f"---\ntitle: Cifras del método\ncreated: {date.today()}\nupdated: {date.today()}\ntype: concept\ntags: [resultado]\n"
        f"sources: [queries/semana-*]\nconfidence: high\n---\n\n# Cifras del método (últimas 12 semanas)\n\n"
        "| semana | etapas | verificación pide cambios | puertas | horas hasta decidir | incidencias | $ etapas |\n"
        "|---|---|---|---|---|---|---|\n" + "\n".join(filas) + "\n")
    idx = w / "index.md"
    s = idx.read_text() if idx.exists() else "# Wiki\n\n## Concepts\n\n## Queries\n"
    if "[[metodo-cifras]]" not in s:
        s = s.replace("## Concepts\n", "## Concepts\n- [[metodo-cifras]] — cifras del método, semana a semana\n", 1)
        idx.write_text(s)
    if (w / ".git").exists():
        subprocess.run(["git", "-C", str(w), "add", "-A"], capture_output=True)
        subprocess.run(["git", "-C", str(w), "-c", "user.name=hermes-seo", "-c", "user.email=hermes-seo@localhost", "commit", "-q",
                        "-m", f"cuaderno: {nombre}"], capture_output=True)
    return f


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["apuntar"]:
        print(f"📓 {apuntar(int(a[a.index('--dias') + 1]) if '--dias' in a else 7)}")
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
