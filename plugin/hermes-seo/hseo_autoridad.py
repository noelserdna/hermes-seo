"""Autoridad y presencia: estar donde los buscadores y las IA buscan las respuestas (listas, directorios, comparativas,
foros), no solo en la propia web. Sustituye a «difusión».

  citas      (sin modelo, «prepara: citas»): de las rondas de visibilidad en IA guardadas (datos/ia/*.json), qué dominios
             de terceros se citan o salen arriba donde la web NO sale, contados y clasificados → datos-citas.json
  gestiones  la etapa (seo-investigador) visita las mejores fuentes y deja ≤4 gestiones en gestiones.json:
             {n, destino, url, tipo, quien: sistema|persona, texto, por_que, como_se_mide}
  puerta     «📣 Todas / ☑️ Solo algunas (1,3) / ❌ No»: al aprobar, cada gestión va a clientes/<web>/gestiones.jsonl;
             las de «sistema» (cambios en la propia web) se lanzan como cambio-seo; las de «persona» salen en el parte
             hasta que se marcan hechas (hseo gestion hecha <web> <n> <url>).
Nada se envía solo a terceros: altas, PR a listas ajenas, correos a autores o foros los hace la persona.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse

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
Rechazo = B.Rechazo
MAX_GESTIONES = 4

CLASES = [   # (clase, patrón del dominio o de la URL, ¿accionable?)
    ("lista-o-directorio", r"glama\.ai|lobehub|mcp\.so|smithery|pulsemcp|mcpservers|findskill|mcp\.directory|awesome|/topics/|producthunt|alternativeto", True),
    ("repositorio", r"github\.com|gitlab\.com", True),
    ("foro-o-comunidad", r"reddit\.com|stackoverflow|news\.ycombinator|dev\.to|medium\.com|substack|discord|foro|forum|hashnode", True),
    ("plataforma-de-cursos", r"udemy|platzi|coursera|datacamp|edx|domestika|deeplearning\.ai|linkedin\.com/learning|youtube", False),
    ("documentacion-oficial", r"anthropic\.com|claude\.(ai|com)|openai\.com|modelcontextprotocol\.io|microsoft\.com|google\.com", False),
]


def _clase(url: str) -> tuple[str, bool]:
    for c, pat, acc in CLASES:
        if re.search(pat, url, re.I):
            return c, acc
    return "comparativa-o-blog", True


def citas(slug: str) -> dict:
    cfg = C.leer(slug)
    propio = str(cfg.get("dominio") or "").lower()
    cuenta, ejemplos, respuestas, sin_nosotros = Counter(), {}, 0, 0
    for f in sorted((C.carpeta(slug) / "datos" / "ia").glob("*.json")):
        d = B.leer(f) or {}
        filas = d.get("filas") or d.get("preguntas") or []
        for r in filas:
            urls = [u for u in (r.get("citas") or r.get("top10") or []) if isinstance(u, str)]
            if not urls:
                continue
            respuestas += 1
            if any(propio and propio in u.lower() for u in urls):
                continue
            sin_nosotros += 1
            for u in urls:
                dom = urlparse(u).netloc.lower().removeprefix("www.")
                if not dom or (propio and propio in dom):
                    continue
                cuenta[dom] += 1
                ejemplos.setdefault(dom, {"url": u, "pregunta": str(r.get("pregunta", ""))[:160]})
    fuentes = []
    for dom, n in cuenta.most_common(30):
        clase, acc = _clase(ejemplos[dom]["url"])
        fuentes.append({"dominio": dom, "veces": n, "clase": clase, "accionable": acc, **ejemplos[dom]})
    return {"respuestas": respuestas, "sin_la_web": sin_nosotros, "fuentes": fuentes,
            "accionables": [x for x in fuentes if x["accionable"]][:12]}


def _gestiones(slug: str, eid: str) -> list:
    d = B.leer(C.carpeta(slug) / "encargos" / eid / "gestiones.json")
    g = d.get("gestiones") if isinstance(d, dict) else d
    if not isinstance(g, list) or not g:
        raise Rechazo("El encargo no dejó gestiones.json con las gestiones")
    return g[:MAX_GESTIONES]


def aplicar(slug: str, eid: str, seleccion: list | None, firma: str) -> str:
    """Lo aprobado en la puerta: se apuntan las gestiones elegidas; las del sistema se lanzan; las de la persona, al parte."""
    gs = _gestiones(slug, eid)
    elegidas = [g for i, g in enumerate(gs, 1) if seleccion is None or i in seleccion]
    E = _cargar("hseo_encargos")
    lanzadas, tuyas, fallidas = [], [], []
    for g in elegidas:
        reg = {"ts": B.ahora(), "encargo": eid, "n": g.get("n"), "destino": g.get("destino"), "url": g.get("url"),
               "tipo": g.get("tipo"), "quien": g.get("quien"), "texto": str(g.get("texto", ""))[:3000],
               "como_se_mide": g.get("como_se_mide"), "estado": "pendiente", "firma": firma}
        if g.get("quien") == "sistema":
            try:
                e = E.lanzar(slug, "cambio-seo", {"que": f"Gestión de autoridad: {g.get('destino')}. {g.get('texto', '')}"[:1500]},
                             quien=f"autoridad ({firma})", en_lugar_de=eid)
                reg.update(estado="lanzada", lanzado=e["id"]); lanzadas.append(e["id"])
            except Rechazo as x:
                reg.update(estado="no-lanzada", motivo=str(x)[:200]); fallidas.append(f"{g.get('destino')} ({str(x)[:120]})")
        else:
            tuyas.append(str(g.get("destino")))
        B.anotar(C.carpeta(slug) / "gestiones.jsonl", reg)
    return (f"{len(elegidas)} gestión(es): " + (f"lanzadas {', '.join(lanzadas)}" if lanzadas else "ninguna del sistema lanzada")
            + (f"; ⚠️ sin lanzar: {'; '.join(fallidas)}" if fallidas else "")
            + (f"; tuyas: {', '.join(tuyas)} (salen en el parte)" if tuyas else ""))


def pendientes_persona(slug: str) -> list:
    filas = _cargar("hseo_estado")._jsonl(C.carpeta(slug) / "gestiones.jsonl")
    hechas = {(r.get("encargo"), r.get("n")) for r in filas if r.get("estado") == "hecha"}
    return [r for r in filas if r.get("quien") == "persona" and r.get("estado") == "pendiente" and (r.get("encargo"), r.get("n")) not in hechas]


def hecha(slug: str, n: int, url: str = "", encargo: str = "") -> str:
    p = [r for r in pendientes_persona(slug) if r.get("n") == n and (not encargo or r.get("encargo") == encargo)]
    if not p:
        raise Rechazo(f"No hay una gestión tuya pendiente con el número {n}")
    r = p[-1]
    B.anotar(C.carpeta(slug) / "gestiones.jsonl", {**r, "ts": B.ahora(), "estado": "hecha", "url_resultado": url})
    return f"✅ Gestión {n} ({r.get('destino')}) hecha" + (f": {url}" if url else "")


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["citas"] and len(a) == 2:
        print(json.dumps(citas(a[1]), ensure_ascii=False, indent=1))
    elif a[:1] == ["pendientes"] and len(a) == 2:
        for r in pendientes_persona(a[1]):
            print(f"{r.get('n')}. {r.get('destino')} ({r.get('tipo')}): {str(r.get('texto'))[:120]}")
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
