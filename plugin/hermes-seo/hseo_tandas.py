"""Tandas: mejorar páginas por grupos (no de una en una) con un grupo de control, para poder medir el efecto.

Una tanda = unas pocas páginas tratadas (≤4) + páginas de control parecidas que no se tocan + lo de antes guardado +
una ventana de medida (28 días si es título/meta, 56 si es contenido). Vive en clientes/<web>/tandas/<id>.json.
Las elige el código (no un modelo) desde metricas.db; el trabajo lo hace la pipeline cambio-seo en un solo encargo.

  hseo_tandas.py proponer <web>          candidatas y control (no crea nada)
  hseo_tandas.py crear <web>             crea la tanda siguiente con lo propuesto (guarda título, meta y H1 de antes)
  hseo_tandas.py lanzar <web> <id>       lanza su encargo (cambio-seo) y lo apunta en la tanda
  hseo_tandas.py lista <web>  ·  hseo_tandas.py veredicto <web> <id>

Límites (se comprueban al crear y al lanzar): como mucho 4 páginas por tanda, las páginas en ventana abierta no
pasan del 40 % de las impresiones de la web, una página no está en dos tandas abiertas (ni como control).
"""
from __future__ import annotations

import html
import importlib.util
import json
import math
import os
import re
import sys
import time
import urllib.request
from datetime import date, timedelta
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
D = _cargar("hseo_datos")
Rechazo = B.Rechazo
MAX_PAGINAS = 4
MAX_CUOTA = 0.40
MIN_IMPRESIONES = 100
MIN_DIAS = 21
VENTANA = {"titulo-meta": 28, "contenido": 56, "enlaces": 56}


def _dir(slug: str) -> Path:
    return C.carpeta(slug) / "tandas"


def _norm(u: str) -> str:
    return str(u or "").rstrip("/")


def listar(slug: str) -> list:
    d = _dir(slug)
    return [B.leer(f) for f in sorted(d.glob("T*.json")) if not f.stem.endswith("-veredicto")] if d.is_dir() else []


def abiertas(slug: str) -> list:
    return [t for t in listar(slug) if t and t.get("estado", "abierta") == "abierta"]


def _ocupadas(slug: str) -> set:
    s = set()
    for t in abiertas(slug):
        s |= {_norm(p["url"]) for p in t.get("paginas", [])} | {_norm(u) for u in t.get("control", [])}
    hace = time.time() - 28 * 86400
    for r in _cargar("hseo_estado")._jsonl(C.carpeta(slug) / "cambios.jsonl"):
        if _cargar("hseo_estado")._ts(r.get("ts")) >= hace:
            s |= {_norm(u) for u in [r.get("url")] + (r.get("urls") or []) if u}
    return s


def _paginas(slug: str) -> tuple[list, int]:
    """Páginas de los últimos 28 días con días de datos y estabilidad (impresiones de la 1.ª mitad frente a la 2.ª)."""
    con = D._db(slug)
    fin = D._ultimo(con)
    if not fin:
        con.close()
        return [], 0
    a, m, b = (fin - timedelta(days=27)).isoformat(), (fin - timedelta(days=14)).isoformat(), fin.isoformat()
    total = int(con.execute("SELECT COALESCE(SUM(impresiones),0) FROM gsc_dia WHERE fecha BETWEEN ? AND ?", (a, b)).fetchone()[0])
    filas = con.execute(
        "SELECT pagina, SUM(clics), SUM(impresiones), SUM(posicion*impresiones)/NULLIF(SUM(impresiones),0), COUNT(DISTINCT fecha), "
        "SUM(CASE WHEN fecha <= ? THEN impresiones ELSE 0 END) FROM gsc_pagina WHERE fecha BETWEEN ? AND ? GROUP BY pagina",
        (m, a, b)).fetchall()
    con.close()
    out = []
    for url, c, i, pos, dias, prim in filas:
        seg = i - prim
        out.append({"url": url, "clics": int(c), "impresiones": int(i), "posicion": round(pos, 1) if pos else None, "dias": dias,
                    "estable": bool(prim and seg and 0.5 <= seg / prim <= 2.0),
                    "esperados": round(i * D.ctr_esperado(pos), 1)})
    return out, total


def _excluida(url: str) -> bool:
    ruta = "/" + url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url
    return ruta in ("/", "") or ruta.startswith(("/blog/tema/", "/tag/", "/categoria/"))


def proponer(slug: str, n: int = 3) -> dict:
    pags, total = _paginas(slug)
    ocup = _ocupadas(slug)
    validas = [p for p in pags if not _excluida(p["url"]) and _norm(p["url"]) not in ocup and p["posicion"]
               and p["impresiones"] >= MIN_IMPRESIONES and p["dias"] >= MIN_DIAS and p["estable"]]
    cand = sorted([p for p in validas if 4 <= p["posicion"] <= 20 and p["clics"] < p["esperados"]],
                  key=lambda p: p["esperados"] - p["clics"], reverse=True)
    tratadas = cand[:min(n, MAX_PAGINAS)]
    for p in tratadas:
        p["jugada"] = "titulo-meta" if p["posicion"] <= 7 else ("contenido" if p["posicion"] <= 15 else "enlaces")
    usados = {_norm(p["url"]) for p in tratadas}
    pos_media = sum(p["posicion"] for p in tratadas) / len(tratadas) if tratadas else 8
    control = sorted([p for p in pags if _norm(p["url"]) not in usados | ocup and not _excluida(p["url"]) and p["posicion"]
                      and p["impresiones"] >= 50 and p["dias"] >= MIN_DIAS and p["estable"]],
                     key=lambda p: abs(p["posicion"] - pos_media))[:6]
    return {"tratadas": tratadas, "control": control, "total_impresiones": total}


def _antes(url: str) -> dict:
    if os.environ.get("HSEO_SIN_RED"):
        return {}
    try:
        r = urllib.request.Request(url, headers={"User-Agent": "hermes-seo/0.1 (lectura)"})
        h = urllib.request.urlopen(r, timeout=20).read().decode("utf-8", "replace")
        t = re.search(r"<title>(.*?)</title>", h, re.S)
        d = re.search(r'<meta name="description" content="(.*?)"', h)
        h1 = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S)
        return {"title": html.unescape(t.group(1).strip()) if t else "", "meta": html.unescape(d.group(1)) if d else "",
                "h1": re.sub(r"<[^>]+>", "", html.unescape(h1.group(1))).strip() if h1 else ""}
    except Exception as e:   # noqa: BLE001
        return {"error": str(e)[:120]}


def limites(slug: str, urls: list, excluir: str = "") -> None:
    if len(urls) > MAX_PAGINAS:
        raise Rechazo(f"Una tanda lleva como mucho {MAX_PAGINAS} páginas")
    pags, total = _paginas(slug)
    imp = {_norm(p["url"]): p["impresiones"] for p in pags}
    otras = [t for t in abiertas(slug) if t.get("id") != excluir]
    en_ventana = set()
    for t in otras:
        en_ventana |= {_norm(p["url"]) for p in t.get("paginas", [])}
        choque = {_norm(u) for u in urls} & ({_norm(p["url"]) for p in t.get("paginas", [])} | {_norm(u) for u in t.get("control", [])})
        if choque:
            raise Rechazo(f"{', '.join(sorted(choque))} ya está en la tanda {t['id']} (tratada o de control)")
    cuota = sum(imp.get(u, 0) for u in en_ventana | {_norm(u) for u in urls}) / total if total else 0
    if cuota > MAX_CUOTA:
        raise Rechazo(f"Con esta tanda, el {cuota:.0%} de las impresiones estaría en ventana abierta (máximo {MAX_CUOTA:.0%})")


def crear(slug: str, propuesta: dict | None = None) -> dict:
    pr = propuesta or proponer(slug)
    if not pr["tratadas"]:
        raise Rechazo("No hay páginas candidatas (≥100 impresiones, 21 días de datos, estables, posición 4-20 y pocos clics)")
    limites(slug, [p["url"] for p in pr["tratadas"]])
    n = len(listar(slug)) + 1
    tid = f"T{n}"
    while (_dir(slug) / f"{tid}.json").exists():
        n += 1; tid = f"T{n}"
    jugada = pr["tratadas"][0].get("jugada", "titulo-meta")
    t = {"id": tid, "estado": "abierta", "creada": date.today().isoformat(), "jugada": jugada,
         "ventana_dias": VENTANA.get(jugada, 28), "tipo": "mejora medida con grupo de control",
         "paginas": [{"url": p["url"], "jugada": p.get("jugada"), "antes": _antes(p["url"]),
                      "linea_base": {k: p[k] for k in ("impresiones", "clics", "posicion")}} for p in pr["tratadas"]],
         "control": [p["url"] for p in pr["control"]]}
    _dir(slug).mkdir(parents=True, exist_ok=True)
    B.escribir(_dir(slug) / f"{tid}.json", t)
    return t


def leer(slug: str, tid: str) -> dict:
    t = B.leer(_dir(slug) / f"{tid}.json")
    if not t:
        raise Rechazo(f"No existe la tanda {tid}")
    return t


def lanzar(slug: str, tid: str, quien: str = "") -> dict:
    t = leer(slug, tid)
    if t.get("encargo"):
        return {"id": t["encargo"], "duplicado": True}
    limites(slug, [p["url"] for p in t["paginas"]], excluir=tid)
    lineas = [f"({i}) {p['url']}: {p['linea_base']['impresiones']} impresiones y {p['linea_base']['clics']} clics en 28 días, "
              f"posición {p['linea_base']['posicion']}" for i, p in enumerate(t["paginas"], 1)]
    que = (f"Tanda {tid} ({t['jugada']}; mejora de resultados en Google, {len(t['paginas'])} páginas en un solo PR). Para cada una: "
           "título (40-60 caracteres) y meta descripción que respondan mejor a lo que se busca, primer párrafo con la respuesta "
           "arriba, y 2-4 enlaces internos entrantes desde páginas relacionadas. Páginas: " + "; ".join(lineas) +
           f". Lo de antes está guardado en tandas/{tid}.json. NO tocar las páginas de control: " +
           ", ".join(t["control"]) + f". Hipótesis: más clics a igual posición en {t['ventana_dias']} días.")
    e = _cargar("hseo_encargos").lanzar(slug, "cambio-seo", {"que": que}, quien=quien or "tanda")
    t["encargo"] = e["id"]
    B.escribir(_dir(slug) / f"{tid}.json", t)
    return e


def veredicto(slug: str, tid: str, hoy: date | None = None) -> dict:
    """Sin modelo. Día 0 = publicación + 3 días. Clics esperados de las tratadas = sus impresiones después × su CTR
    antes × (CTR del control después / antes). z = (observados − esperados) / √esperados. Tres salidas."""
    t = leer(slug, tid)
    pub = next((r for r in _cargar("hseo_estado")._jsonl(C.carpeta(slug) / "cambios.jsonl")
                if t.get("encargo") and r.get("encargo") == t["encargo"]), None)
    if not pub:
        return {"tanda": tid, "listo": False, "motivo": "aún no está publicada"}
    d0 = date.fromisoformat(pub["ts"][:10]) + timedelta(days=3)
    v = int(t.get("ventana_dias") or 28)
    con = D._db(slug)
    ultimo = D._ultimo(con)
    if not ultimo or (ultimo - d0).days < v - 1:
        con.close()
        return {"tanda": tid, "listo": False, "motivo": f"faltan datos: la ventana acaba el {(d0 + timedelta(days=v - 1)).isoformat()}"}
    antes = ((d0 - timedelta(days=v + 3)).isoformat(), (d0 - timedelta(days=4)).isoformat())
    despues = (d0.isoformat(), (d0 + timedelta(days=v - 1)).isoformat())

    def suma(urls, rango):
        c = i = 0
        for u in urls:
            s = D._suma(con, *rango, pagina=u)
            c += s["clics"]; i += s["impresiones"]
        return c, i
    tr = [p["url"] for p in t["paginas"]]
    ca, ia = suma(tr, antes); cd, id_ = suma(tr, despues)
    kca, kia = suma(t["control"], antes); kcd, kid = suma(t["control"], despues)
    con.close()
    ctr_a = ca / ia if ia else 0
    factor = ((kcd / kid) / (kca / kia)) if kia and kid and kca else 1.0
    esperados = id_ * ctr_a * factor
    z = (cd - esperados) / math.sqrt(esperados) if esperados > 0 else 0.0
    if min(ia, id_) < 1000 or esperados < 10:
        salida, expl = "no-se-puede-saber", f"muy pocos datos ({ia} y {id_} impresiones; {esperados:.1f} clics esperados)"
    elif z >= 1.64:
        salida, expl = "funciono", f"{cd} clics frente a {esperados:.1f} esperados (z {z:.2f})"
    else:
        salida = "empeoro" if z <= -1.64 else "no-funciono"
        expl = f"{cd} clics frente a {esperados:.1f} esperados (z {z:.2f})"
    r = {"tanda": tid, "listo": True, "ts": B.ahora(), "salida": salida, "explicacion": expl, "z": round(z, 2),
         "tratadas": {"antes": [ca, ia], "despues": [cd, id_]}, "control": {"antes": [kca, kia], "despues": [kcd, kid]},
         "esperados": round(esperados, 1)}
    B.escribir(_dir(slug) / f"{tid}-veredicto.json", r)
    t["estado"] = "cerrada"
    B.escribir(_dir(slug) / f"{tid}.json", t)
    try:
        _cargar("hseo_wiki").regenerar_cambios(slug)
    except Exception:   # noqa: BLE001
        pass
    if salida == "empeoro":
        try:
            _cargar("hseo_puertas").abrir(slug, tipo="mantenimiento", titulo=f"🩺 La tanda {tid} empeoró los clics",
                                         texto=f"{expl}. Lo de antes está guardado en tandas/{tid}.json: se puede volver atrás.",
                                         hallazgos=[{"url": u, "accion": "revertir", "a": "lo guardado en la tanda"} for u in tr])
        except Exception:   # noqa: BLE001
            pass
    return r


def vencidas(slug: str) -> list:
    """Lo llama la recogida diaria: da el veredicto de las tandas publicadas cuya ventana ya acabó."""
    out = []
    for t in abiertas(slug):
        if t.get("encargo"):
            r = veredicto(slug, t["id"])
            if r.get("listo"):
                out.append(r)
    return out


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    try:
        if a[:1] == ["proponer"] and len(a) == 2:
            print(json.dumps(proponer(a[1]), ensure_ascii=False, indent=1))
        elif a[:1] == ["crear"] and len(a) == 2:
            print(json.dumps(crear(a[1]), ensure_ascii=False, indent=1))
        elif a[:1] == ["lanzar"] and len(a) == 3:
            e = lanzar(a[1], a[2])
            print(f"🚀 Tanda {a[2]}: encargo {e['id']}" + (" (ya estaba)" if e.get("duplicado") else ""))
        elif a[:1] == ["lista"] and len(a) == 2:
            for t in listar(a[1]):
                print(f"{t['id']:4} {t.get('estado', 'abierta'):8} {t.get('jugada', '')}: {len(t.get('paginas', []))} páginas, "
                      f"control {len(t.get('control', []))}, encargo {t.get('encargo') or '—'}")
        elif a[:1] == ["veredicto"] and len(a) == 3:
            print(json.dumps(veredicto(a[1], a[2]), ensure_ascii=False, indent=1))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
