"""El parte semanal de una web, sin modelo: cifras, lo hecho, lo pendiente y hasta 3 propuestas que se aprueban con
«haz la N». Lo lanza un cron --no-agent los lunes (su salida es el mensaje) y se guarda en
clientes/<web>/informes/partes/<fecha>.json (+ ultimo.json, que leen el estado por turno y «hseo propuesta»).

  hseo_parte.py generar <web> [--no-guardar]     imprime el parte (texto para Telegram)
  hseo_parte.py propuesta <web> <n>              ejecuta la propuesta n del último parte (una vez)

Las propuestas salen de un catálogo cerrado; el texto y la orden los compone el código (nunca un modelo), y cada orden
se valida antes de ofrecerla (la pipeline existe, las políticas la dejan y no está ya en marcha).
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import date, datetime, timezone
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
E = _cargar("hseo_encargos")
PL = _cargar("hseo_pipelines")
PU = _cargar("hseo_puertas")
ES = _cargar("hseo_estado")
Rechazo = B.Rechazo
MAX_PROPUESTAS = 3
DIAS = 7


def _carpeta(slug: str) -> Path:
    return C.carpeta(slug) / "informes" / "partes"


def _miles(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _dec(x) -> str:
    return str(x).replace(".", ",")


def _var(a: float, b: float) -> str:
    if not b:
        return ""
    v = (a - b) / b * 100
    return f" ({'+' if v >= 0 else ''}{v:.0f} %)"


def _valida(slug: str, pid: str, params: dict) -> bool:
    try:
        PL.plan(pid, slug)
        PL.politicas(pid, slug)
        p = PL.cargar(pid, slug)
        if [k for k in (p.get("parametros") or {}) if k not in params]:
            return False
        return E.duplicado(slug, pid, params) is None
    except Rechazo:
        return False


def _ruta(url: str) -> str:
    return "/" + url.split("://", 1)[-1].split("/", 1)[-1] if "://" in url else url


def propuestas(slug: str, r: dict) -> list:
    """Catálogo cerrado, ordenado por clics que podría ganar; como mucho una de título y MAX_PROPUESTAS en total."""
    cand = []
    en_marcha = json.dumps([e.get("params") for e in E.listar(slug, abiertos=True)], ensure_ascii=False)
    # una página con un cambio publicado hace menos de 28 días no se vuelve a tocar (se mezclarían los efectos)
    hace = time.time() - 28 * 86400
    recientes = [str(x.get("url") or "").rstrip("/") for x in ES._jsonl(C.carpeta(slug) / "cambios.jsonl") if ES._ts(x.get("ts")) >= hace]
    en_marcha += " " + " ".join(recientes + [_ruta(u) for u in recientes if u])
    if r.get("hay_datos"):
        for p in r.get("bajo_ctr") or []:   # muchas impresiones y pocos clics para su posición
            url = p["pagina"]
            if url.rstrip("/") in en_marcha or _ruta(url).rstrip("/") in en_marcha:
                continue
            params = {"que": f"Título, meta descripción y primer párrafo de {url}: tiene {_miles(p['impresiones'])} "
                             f"impresiones y {p['clics']} clics en 28 días en la posición {p['posicion']}; con esa posición "
                             f"se esperarían unos {p['clics_esperados']:.0f}. Que el resultado de Google responda mejor a lo que se busca."}
            cand.append({"id": "bajo-ctr", "titulo": True, "valor": p["clics_esperados"] - p["clics"],
                         "texto": f"Mejorar el título y la entrada de {_ruta(url)} ({_miles(p['impresiones'])} impresiones, "
                                  f"{p['clics']} clics, posición {_dec(p['posicion'])})",
                         "orden": {"tipo": "lanzar", "pipeline": "cambio-seo", "params": params}})
        for q in (r.get("pagina_dos") or [])[:5]:   # consultas en posiciones 8-20: de la página 2 a la 1
            url = q.get("pagina") or ""
            if not url or url.rstrip("/") in en_marcha or _ruta(url).rstrip("/") in en_marcha:
                continue
            params = {"url": url, "motivo": f"La consulta «{q['consulta']}» tiene {q['impresiones']} impresiones en la "
                                            f"posición {q['posicion']}: llevarla a la primera página."}
            cand.append({"id": "pagina-dos", "titulo": False, "valor": q["impresiones"] * 0.03,
                         "texto": f"Llevar «{q['consulta']}» a la primera página ({q['impresiones']} impresiones, posición {_dec(q['posicion'])})",
                         "orden": {"tipo": "lanzar", "pipeline": "actualizacion", "params": params}})
    try:   # la tanda siguiente: varias páginas a la vez, con grupo de control (mejor que una suelta)
        T = _cargar("hseo_tandas")
        if not [t for t in T.abiertas(slug) if not t.get("encargo")]:
            pr = T.proponer(slug)
            if len(pr["tratadas"]) >= 2:
                T.limites(slug, [p["url"] for p in pr["tratadas"]])
                cand.append({"id": "tanda", "titulo": True, "valor": sum(p["esperados"] - p["clics"] for p in pr["tratadas"]),
                             "texto": f"Mejorar en tanda {len(pr['tratadas'])} páginas con muchas impresiones y pocos clics ("
                                      + ", ".join(_ruta(p["url"]) for p in pr["tratadas"]) + "), con grupo de control",
                             "orden": {"tipo": "tanda"}})
    except Exception:   # noqa: BLE001 — sin datos o fuera de límites: no se propone
        pass
    if not any(e.get("pipeline") == "estrategia" for e in E.listar(slug)):
        cand.append({"id": "sin-mapa", "titulo": False, "valor": 5,
                     "texto": "Hacer la estrategia y el mapa de temas (aún no hay)",
                     "orden": {"tipo": "lanzar", "pipeline": "estrategia", "params": {}}})
    for e in E.listar(slug, abiertos=True):
        if e.get("estado") == "parado":
            cand.append({"id": "parada", "titulo": False, "valor": 3,
                         "texto": f"Reintentar «{e.get('nombre')}», que está parado",
                         "orden": {"tipo": "reintentar", "encargo": e["id"]}})
    out, titulo = [], False
    for c in sorted(cand, key=lambda c: c["valor"], reverse=True):
        if c["titulo"] and titulo:
            continue
        o = c["orden"]
        if o["tipo"] == "tanda" and not _valida(slug, "cambio-seo", {"que": "x"}):
            continue
        if o["tipo"] == "lanzar" and not _valida(slug, o["pipeline"], o["params"]):
            continue
        titulo = titulo or c["titulo"]
        out.append({k: c[k] for k in ("id", "texto", "orden")})
        if len(out) == MAX_PROPUESTAS:
            break
    return out


def generar(slug: str, ahora: float | None = None) -> dict:
    ahora = ahora or time.time()
    cfg = C.leer(slug)
    d = C.carpeta(slug)
    faltan = []
    r = {}
    try:
        r = _cargar("hseo_datos").resumen(slug, 28)
    except Exception as e:   # noqa: BLE001 — el parte sale aunque falten datos
        faltan.append(f"Search Console ({e})")
    if not r.get("hay_datos"):
        faltan.append("Search Console (no hay datos guardados)")
    elif r.get("hasta") and (date.today() - date.fromisoformat(r["hasta"])).days > 5:
        faltan.append(f"Search Console (los datos llegan hasta el {r['hasta']})")
    desde = ahora - DIAS * 86400
    hecho = []
    for e in E.listar(slug):
        if e.get("informe") and ES._ts(e.get("creado")) >= desde:
            hecho.append(e.get("nombre"))
    publicado = [x for x in ES._jsonl(d / "cambios.jsonl") if ES._ts(x.get("ts")) >= desde]
    puertas = [p for p in PU.puertas(("abierta",)) if p.get("cliente") == slug]
    inc = [B.leer(f) or {} for f in sorted((d / "incidencias").glob("*.json"))] if (d / "incidencias").is_dir() else []
    resueltas = [i for i in inc if i.get("estado") == "resuelta" and i.get("sola") and ES._ts(i.get("resuelta")) >= desde]
    criterio = cfg.get("criterio") if isinstance(cfg.get("criterio"), dict) else None
    return {"web": slug, "nombre": cfg.get("nombre") or slug, "fecha": datetime.now(timezone.utc).date().isoformat(),
            "cifras": r if r.get("hay_datos") else None, "faltan": faltan, "hecho": hecho,
            "publicado": [{"url": x.get("url"), "clase": x.get("clase")} for x in publicado],
            "puertas": [{"id": p["id"], "titulo": p["titulo"], "creada": p.get("creada")} for p in puertas],
            "resueltas": [i.get("texto", "") for i in resueltas], "criterio": criterio,
            "propuestas": propuestas(slug, r)}


def texto(parte: dict) -> str:
    l = [f"📊 Parte de la semana · {parte['nombre']}"]
    c = parte.get("cifras")
    if c:
        a, b = c["actual"], c["anterior"]
        l.append(f"Google, 28 días hasta el {c['hasta']}: {_miles(a['clics'])} clics{_var(a['clics'], b['clics'])} · "
                 f"{_miles(a['impresiones'])} impresiones{_var(a['impresiones'], b['impresiones'])} · "
                 f"{_dec(a['ctr'])} % de clic · posición {_dec(a['posicion'])}")
    for f in parte.get("faltan") or []:
        l.append(f"⚠️ Falta: {f}")
    if parte.get("hecho"):
        l.append("Hecho: " + ", ".join(sorted(set(parte["hecho"]))))
    if parte.get("publicado"):
        l.append("Publicado: " + ", ".join(_ruta(p["url"] or p["clase"] or "") for p in parte["publicado"]))
    if parte.get("resueltas"):
        l.append(f"Incidencias resueltas solas: {len(parte['resueltas'])}")
    l.append(f"Pendiente de decidir: {len(parte['puertas'])}" + (" (" + "; ".join(p["titulo"][:50] for p in parte["puertas"]) + ")" if parte["puertas"] else ""))
    if parte.get("propuestas"):
        l.append("")
        l.append("Propuestas (responde «haz la 1», «haz la 2»…):")
        l += [f"{i}. {p['texto']}" for i, p in enumerate(parte["propuestas"], 1)]
    else:
        l.append("Nada que proponer esta semana.")
    cr = parte.get("criterio")
    if cr and c:
        l.append(f"🎯 Criterio del {cr.get('fecha', '?')}: {_miles(c['actual']['clics'])} de {cr.get('objetivo_clics', '?')} clics")
    return "\n".join(l)


def guardar(slug: str, parte: dict) -> Path:
    d = _carpeta(slug)
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{parte['fecha']}.json"
    B.escribir(f, parte)
    B.escribir(d / "ultimo.json", parte)
    return f


def ejecutar_propuesta(slug: str, n: int, quien: str = "") -> str:
    parte = B.leer(_carpeta(slug) / "ultimo.json")
    if not isinstance(parte, dict) or not parte.get("propuestas"):
        raise Rechazo(f"{slug} no tiene propuestas en su último parte")
    if not 1 <= n <= len(parte["propuestas"]):
        raise Rechazo(f"El parte del {parte.get('fecha')} tiene {len(parte['propuestas'])} propuesta(s)")
    p = parte["propuestas"][n - 1]
    if p.get("hecha"):
        return f"La propuesta {n} ya se lanzó ({p['hecha']})."
    o = p["orden"]
    if o["tipo"] == "lanzar":
        e = E.lanzar(slug, o["pipeline"], o.get("params") or {}, quien=quien or "parte")
        res = f"ya estaba en marcha ({e['id']})" if e.get("duplicado") else f"lanzado {e['id']}"
    elif o["tipo"] == "tanda":
        T = _cargar("hseo_tandas")
        t = T.crear(slug)
        e = T.lanzar(slug, t["id"], quien=quien or "parte")
        res = f"tanda {t['id']} lanzada ({e['id']})"
    elif o["tipo"] == "reintentar":
        enc = E.leer(slug, o["encargo"])
        fallos = [x for x in ES._jsonl(C.carpeta(slug) / "etapas.jsonl") if x.get("encargo") == enc["id"] and x.get("resultado") != "done"]
        parada = fallos[-1]["etapa"] if fallos else enc["etapas"][-1]["id"]
        _cargar("hseo_cli").reintentar(slug, enc["id"], parada)
        res = f"reintentado {enc['id']} desde {parada}"
    else:
        raise Rechazo("Propuesta sin orden conocida")
    p["hecha"] = f"{B.ahora()} · {res}"
    B.escribir(_carpeta(slug) / "ultimo.json", parte)
    return f"✅ Propuesta {n}: {p['texto']} → {res}"


def main(argv=None) -> int:
    a = (argv if argv is not None else sys.argv[1:])
    try:
        if a[:1] == ["generar"] and len(a) >= 2:
            parte = generar(a[1])
            if "--no-guardar" not in a:
                guardar(a[1], parte)
            print(texto(parte))
        elif a[:1] == ["propuesta"] and len(a) == 3:
            print(ejecutar_propuesta(a[1], int(a[2])))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
