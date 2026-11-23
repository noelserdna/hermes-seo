"""El parte semanal de una web, sin modelo: cifras, lo hecho, lo pendiente y hasta 3 propuestas que se aprueban con
«haz la N». Lo lanza un cron --no-agent los lunes (su salida es el mensaje) y se guarda en
clientes/<web>/informes/partes/<fecha>.json (+ ultimo.json, que leen el estado por turno y «hseo propuesta»).

  hseo_parte.py generar <web> [--no-guardar]     imprime el parte (texto para Telegram)
  hseo_parte.py ver <web>                        el último parte guardado, sin tocar nada
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
# Mínimos para proponer a partir de Search Console. Por debajo, la cifra es ruido y la propuesta cuesta una pipeline entera.
DIAS_ARRANQUE = 28        # días con datos antes de proponer nada basado en búsquedas (web nueva: «arranque»)
MIN_IMP_PAGINA_DOS = 50   # impresiones en 28 días de una consulta en posiciones 8-20
MIN_IMP_LEJOS = 20        # impresiones de la consulta objetivo cuando la página está más allá del puesto 20
MIN_GANANCIA_CTR = 3      # clics que faltan frente a lo esperado para proponer título y entrada
OBJETIVO_POS = 5          # «llevar a la primera página» se valora como llegar al puesto 5


def _tokens(t: str) -> set:
    import unicodedata
    t = unicodedata.normalize("NFD", str(t).lower())
    t = "".join(c if c.isalnum() else " " for c in t if unicodedata.category(c) != "Mn")
    return {x for x in t.split() if x}


def _objetivo(consulta: str, url: str) -> bool:
    """¿Es la consulta que esa página debería ganar? Las palabras de su dirección y las de la consulta son las mismas
    (unas contienen a las otras) y hay al menos dos: /blog/que-es-mcp ↔ «que es mcp», «mcp que es», «que es un mcp»."""
    slug = _tokens(_ruta(url).rstrip("/").rsplit("/", 1)[-1].rsplit(".", 1)[0])
    q = _tokens(consulta)
    return len(slug & q) >= 2 and (slug <= q or q <= slug)


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


def propuestas(slug: str, r: dict, sin_gsc: bool = False) -> list:
    """Catálogo cerrado, ordenado por clics que podría ganar; como mucho una de título y MAX_PROPUESTAS en total."""
    cand = []
    en_marcha = json.dumps([e.get("params") for e in E.listar(slug, abiertos=True)], ensure_ascii=False)
    # una página con un cambio publicado hace menos de 28 días no se vuelve a tocar (se mezclarían los efectos)
    hace = time.time() - 28 * 86400
    recientes = [str(x.get("url") or "").rstrip("/") for x in ES._jsonl(C.carpeta(slug) / "cambios.jsonl") if ES._ts(x.get("ts")) >= hace]
    en_marcha += " " + " ".join(recientes + [_ruta(u) for u in recientes if u])
    # lo que la persona descartó hace poco no se le vuelve a proponer (lo acaba de decir que no)
    en_marcha += " " + json.dumps([e.get("params") for e in E.listar(slug)
                                   if e.get("estado") == "descartado" and ES._ts(e.get("creado")) >= hace], ensure_ascii=False)
    D = _cargar("hseo_datos")
    marca = [t for t in ((r.get("marca") or {}).get("terminos") or []) if t]
    # sin datos fiables no se propone a partir de búsquedas: web con menos de 28 días de datos, o el acceso caído
    con_gsc = r.get("hay_datos") and not sin_gsc and int((r.get("actual") or {}).get("dias") or 0) >= DIAS_ARRANQUE
    if con_gsc:
        for p in r.get("bajo_ctr") or []:   # muchas impresiones y pocos clics para su posición
            url = p["pagina"]
            if url.rstrip("/") in en_marcha or _ruta(url).rstrip("/") in en_marcha:
                continue
            if (p.get("posicion") or 99) > 10 or p["clics_esperados"] - p["clics"] < MIN_GANANCIA_CTR:
                continue   # fuera de la primera página el título no es el problema; con menos ganancia, es ruido
            params = {"que": f"Título, meta descripción y primer párrafo de {url}: tiene {_miles(p['impresiones'])} "
                             f"impresiones y {p['clics']} clics en 28 días en la posición {p['posicion']}; con esa posición "
                             f"se esperarían unos {p['clics_esperados']:.0f}. Que el resultado de Google responda mejor a lo que se busca."}
            cand.append({"id": "bajo-ctr", "titulo": True, "url": url, "valor": p["clics_esperados"] - p["clics"],
                         "texto": f"Mejorar el título y la entrada de {_ruta(url)} ({_miles(p['impresiones'])} impresiones, "
                                  f"{p['clics']} clics, posición {_dec(p['posicion'])})",
                         "orden": {"tipo": "lanzar", "pipeline": "cambio-seo", "params": params}})
        # la consulta que la página debería ganar y en la que casi no aparece (más allá del puesto 20)
        lejos = {}
        for q in r.get("lejos") or []:
            url = q.get("pagina") or ""
            if url and q["impresiones"] >= MIN_IMP_LEJOS and _objetivo(q["consulta"], url) and url not in lejos:
                lejos[url] = q
        for q in r.get("pagina_dos") or []:   # consultas en posiciones 8-20: de la página 2 a la 1
            url = q.get("pagina") or ""
            if not url or url.rstrip("/") in en_marcha or _ruta(url).rstrip("/") in en_marcha:
                continue
            if q["impresiones"] < MIN_IMP_PAGINA_DOS or any(t in q["consulta"].lower() for t in marca):
                continue
            extra = ""
            if url in lejos:
                x = lejos.pop(url)
                extra = (f" Además, la consulta que esta página debería ganar, «{x['consulta']}», está en la posición "
                         f"{x['posicion']} ({x['impresiones']} impresiones): que la respuesta a esa pregunta sea lo primero.")
            params = {"url": url, "motivo": f"La consulta «{q['consulta']}» tiene {q['impresiones']} impresiones en la "
                                            f"posición {q['posicion']}: llevarla a la primera página.{extra}"}
            ganancia = q["impresiones"] * max(0.0, D.ctr_esperado(OBJETIVO_POS) - D.ctr_esperado(q["posicion"]))
            cand.append({"id": "pagina-dos", "titulo": False, "url": url, "valor": ganancia,
                         "texto": f"Llevar «{q['consulta']}» a la primera página ({q['impresiones']} impresiones, posición {_dec(q['posicion'])})"
                                  + (" y reforzar su consulta objetivo" if extra else ""),
                         "orden": {"tipo": "lanzar", "pipeline": "actualizacion", "params": params}})
        for url, x in lejos.items():
            if url.rstrip("/") in en_marcha or _ruta(url).rstrip("/") in en_marcha:
                continue
            params = {"url": url, "motivo": f"Esta página debería responder a «{x['consulta']}» y está en la posición "
                                            f"{x['posicion']} ({x['impresiones']} impresiones en 28 días): reforzar esa respuesta."}
            # tan lejos, las impresiones se quedan muy cortas frente a la demanda real: se valora como un tercio de ellas en clics
            cand.append({"id": "objetivo-lejos", "titulo": False, "url": url, "valor": x["impresiones"] * 0.3,
                         "texto": f"Reforzar {_ruta(url)} para «{x['consulta']}», su consulta objetivo (posición {_dec(x['posicion'])}, {x['impresiones']} impresiones)",
                         "orden": {"tipo": "lanzar", "pipeline": "actualizacion", "params": params}})
    try:   # la tanda siguiente: varias páginas a la vez, con grupo de control (mejor que una suelta)
        T = _cargar("hseo_tandas")
        if con_gsc and not [t for t in T.abiertas(slug) if not t.get("encargo")]:
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
    out, titulo, urls = [], False, set()
    for c in sorted(cand, key=lambda c: c["valor"], reverse=True):
        if c["titulo"] and titulo:
            continue
        if c.get("url") and c["url"].rstrip("/") in urls:   # una propuesta por página: dos a la vez se pisan
            continue
        o = c["orden"]
        if o["tipo"] == "tanda" and not _valida(slug, "cambio-seo", {"que": "x"}):
            continue
        if o["tipo"] == "lanzar" and not _valida(slug, o["pipeline"], o["params"]):
            continue
        titulo = titulo or c["titulo"]
        if c.get("url"):
            urls.add(c["url"].rstrip("/"))
        out.append({**{k: c[k] for k in ("id", "texto", "orden")}, "codigo": __import__("secrets").token_urlsafe(12)})
        if len(out) == MAX_PROPUESTAS:
            break
    return out


def _analitica(slug: str, faltan: list) -> dict | None:
    if "analitica:mcp" not in C.capacidades(C.leer(slug)):
        return None
    try:
        a = _cargar("hseo_datos").analitica(slug)
    except Exception as e:   # noqa: BLE001
        faltan.append(f"analítica de la web ({e})"); return None
    if not a:
        faltan.append("analítica de la web (aún no hay ninguna foto guardada)")
    return a


def _aplazados(slug: str) -> list:
    try:
        return [{"n": n, "titulo": t, "desde": d, "como": c} for n, t, d, c in _cargar("hseo_aterrizaje").aplazados(slug)]
    except Exception:   # noqa: BLE001
        return []


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
    elif r.get("hasta") and (date.today() - date.fromisoformat(r["hasta"])).days > 4:   # lo normal son 2-3 días de retraso
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
    vivas = [i for i in inc if i.get("estado") in ("viva", "intentando", "avisada")]
    # con el acceso o la recogida de Search Console caídos, las cifras son viejas: no se propone nada a partir de ellas
    sin_gsc = any(i.get("clase") in ("acceso", "datos") or (i.get("clase") == "recogida" and "gsc" in str(i.get("recurso")))
                  for i in vivas)
    dias_datos = int((r.get("actual") or {}).get("dias") or 0) if r.get("hay_datos") else 0
    criterio = cfg.get("criterio") if isinstance(cfg.get("criterio"), dict) else None
    try:
        tuyas = [f"{r.get('n')}. {r.get('destino')}" for r in _cargar("hseo_autoridad").pendientes_persona(slug)]
    except Exception:   # noqa: BLE001
        tuyas = []
    return {"web": slug, "nombre": cfg.get("nombre") or slug, "fecha": datetime.now(timezone.utc).date().isoformat(),
            "cifras": r if r.get("hay_datos") else None, "web_propia": _analitica(slug, faltan), "faltan": faltan, "hecho": hecho,
            "publicado": [{"url": x.get("url"), "clase": x.get("clase")} for x in publicado],
            "puertas": [{"id": p["id"], "titulo": p["titulo"], "creada": p.get("creada")} for p in puertas],
            "resueltas": [i.get("texto", "") for i in resueltas], "criterio": criterio, "gestiones_tuyas": tuyas,
            "aplazados": _aplazados(slug),
            "incidencias": [{"texto": i.get("texto", ""), "desde": str(i.get("creada", ""))[:10], "mano": i.get("mano", "")} for i in vivas],
            "sin_gsc": sin_gsc, "arranque": dias_datos if r.get("hay_datos") and dias_datos < DIAS_ARRANQUE else None,
            "propuestas": propuestas(slug, r, sin_gsc)}


def texto(parte: dict) -> str:
    l = [f"📊 Parte de la semana · {parte['nombre']}"]
    for i in parte.get("incidencias") or []:   # lo roto va lo primero: un aviso suelto se pierde
        l.append(f"🔴 Sin resolver desde el {i['desde']}: {i['texto']}." + (f" Hace falta tu mano: {i['mano']}." if i.get("mano") else ""))
    c = parte.get("cifras")
    w = parte.get("web_propia") or {}
    google = ""
    if c:
        a, b = c["actual"], c["anterior"]
        comparable = b.get("dias", 0) >= 0.9 * a.get("dias", 0)   # 28 días contra 21 no es un «+138 %»
        v = (lambda x, y: _var(x, y)) if comparable else (lambda x, y: "")
        google = (f"Google, 28 días hasta el {c['hasta']}: {_miles(a['clics'])} clics{v(a['clics'], b['clics'])} · "
                  f"{_miles(a['impresiones'])} impresiones{v(a['impresiones'], b['impresiones'])} · "
                  f"{_dec(a['ctr'])} % de clic · posición {_dec(a['posicion'])}"
                  + ("" if comparable or not b.get("dias") else f" (sin comparación: del periodo anterior solo hay {b['dias']} días)"))
    if google and not w.get("mes"):
        l.append(google)
    if w.get("mes"):
        m, p = w["mes"], w.get("anterior") or {}
        l.append(f"La web, {m['mes']} (hasta el {w.get('fecha')}): {_miles(m['visitas'])} visitas · {_miles(m['descargas'])} descargas · "
                 f"{_miles(m['pagos'])} pagos iniciados · {_miles(m['ventas'])} ventas"
                 + (f" (el mes anterior: {_miles(p.get('descargas', 0))} descargas, {_miles(p.get('ventas', 0))} ventas)" if p else ""))
    if w.get("blog"):
        b = w["blog"]
        l.append(f"Blog ({b['publicados']} artículos): {_miles(b['visitas'])} visitas este mes · desde buscadores {_miles(b['buscadores'])} · desde IA {_miles(b['ia'])}")
    if google and w.get("mes"):   # primero lo que vende la web; después, las búsquedas
        l.append(google)
    for f in parte.get("faltan") or []:
        l.append(f"⚠️ Falta: {f}")
    if parte.get("hecho"):
        l.append("Hecho: " + ", ".join(sorted(set(parte["hecho"]))))
    if parte.get("publicado"):
        l.append("Publicado: " + ", ".join(_ruta(p["url"] or p["clase"] or "") for p in parte["publicado"]))
    if parte.get("resueltas"):
        l.append(f"Incidencias resueltas solas: {len(parte['resueltas'])}")
    l.append(f"Pendiente de decidir: {len(parte['puertas'])}" + (" (" + "; ".join(p["titulo"][:50] for p in parte["puertas"]) + ")" if parte["puertas"] else ""))
    for x in parte.get("aplazados") or []:
        l.append(f"⏸ Aplazado del alta desde el {x['desde']}: {x['titulo']}. Cuando puedas: {x['como']}")
    if parte.get("gestiones_tuyas"):
        l.append("Tu parte (autoridad, cuando puedas): " + "; ".join(parte["gestiones_tuyas"]))
    if parte.get("propuestas"):
        l.append("")
        l.append("Propuestas (responde «haz la 1», «haz la 2»…):")
        l += [f"{i}. {p['texto']}" for i, p in enumerate(parte["propuestas"], 1)]
    elif parte.get("sin_gsc"):
        l.append("Sin propuestas esta semana: los datos de Google están parados (arriba) y no propongo sobre cifras viejas.")
    elif parte.get("arranque") is not None:
        l.append(f"🌱 Web en arranque: {parte['arranque']} de {DIAS_ARRANQUE} días de datos de Google. Aún no propongo cambios "
                 f"a partir de búsquedas: con tan poco, cualquier cifra es ruido.")
    else:
        l.append("Nada que proponer esta semana.")
    cr = parte.get("criterio")
    if cr:
        partes = []
        if c and cr.get("objetivo_clics"):
            partes.append(f"{_miles(c['actual']['clics'])} de {cr['objetivo_clics']} clics (28 días)")
        m = (w.get("mes") or {})
        if m and cr.get("objetivo_descargas"):
            partes.append(f"{_miles(m['descargas'])} de {cr['objetivo_descargas']} descargas al mes")
        if m and cr.get("objetivo_ventas"):
            partes.append(f"{_miles(m['ventas'])} de {cr['objetivo_ventas']} ventas al mes")
        if partes:
            l.append(f"🎯 Objetivo del {cr.get('fecha', '?')}: " + " · ".join(partes))
    return "\n".join(l)


def ver(slug: str) -> str:
    """El último parte guardado, tal cual se envió. No genera, no guarda, no envía."""
    parte = B.leer(_carpeta(slug) / "ultimo.json")
    if not isinstance(parte, dict):
        return f"{slug} aún no tiene ningún parte (sale los lunes)."
    return texto(parte) + f"\n\n(parte del {parte.get('fecha')}; vista previa con datos de hoy: hseo parte {slug} --no-guardar)"


def hecho_hoy(slug: str) -> bool:
    return (_carpeta(slug) / f"{datetime.now(timezone.utc).date().isoformat()}.json").exists()


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
        elif a[:1] == ["ver"] and len(a) == 2:
            print(ver(a[1]))
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
