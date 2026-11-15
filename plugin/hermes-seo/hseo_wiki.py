"""La memoria de cada web (su wiki llm-wiki) se escribe SOLA, sin modelo, en momentos fijos, y cada etapa lee lo que
le toca. Las páginas fijas viven en wiki/concepts/:

  negocio.md               la web, su público, su voz, mercados y reglas          ← alta y cambios de configuración
  mapa-tematico.md         qué página responde a qué búsqueda                     ← al cerrar la estrategia
  linea-base.md            cómo estaba la web al empezar                           ← al cerrar la línea base
  decisiones.md            cada puerta decidida: qué, quién, resultado             ← al firmar una puerta
  correcciones.md          lo que la persona pidió cambiar o por qué descartó      ← al firmar una puerta con texto
  cambios-y-veredictos.md  lo publicado, su hipótesis y, a su tiempo, el veredicto ← al publicar y al dar veredicto

Las páginas derivadas (decisiones, correcciones, cambios) se REGENERAN desde los registros (puertas.jsonl,
cambios.jsonl, tandas/): son idempotentes. Nada aquí frena al notario ni a una etapa: cualquier fallo se ignora.
Los números no se copian: se enlazan (datos/, informes, encargos).

  hseo_wiki.py sembrar <web>   ·   hseo_wiki.py para <web> <etapa>
"""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import time
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

PAGINAS = {   # nombre → (título, etiquetas)
    "negocio": ("Negocio, público y voz", ["publico", "voz", "objetivo"]),
    "mapa-tematico": ("Mapa temático", ["mapa-tematico", "canibalizacion"]),
    "linea-base": ("Línea base", ["indexacion", "rendimiento"]),
    "decisiones": ("Decisiones en las puertas", ["decision"]),
    "correcciones": ("Correcciones pedidas por la persona", ["decision", "leccion"]),
    "cambios-y-veredictos": ("Cambios publicados y veredictos", ["hipotesis", "resultado"]),
}
LEE = {   # qué páginas recibe cada etapa (por id de etapa); el resto, «negocio»
    "investigar": ["negocio", "mapa-tematico", "correcciones"], "redactar": ["negocio", "mapa-tematico", "correcciones"],
    "aplicar-cambio": ["negocio", "mapa-tematico", "correcciones"], "analizar-cambio": ["negocio", "mapa-tematico", "cambios-y-veredictos"],
    "plan-tanda": ["negocio", "mapa-tematico", "cambios-y-veredictos"],
    "verificar": ["negocio", "correcciones"], "revisar-lectura": ["negocio", "correcciones"],
    "metricas": ["cambios-y-veredictos", "decisiones", "mapa-tematico"], "revision-mensual": ["cambios-y-veredictos", "decisiones", "mapa-tematico"],
    "veredicto": ["cambios-y-veredictos"], "radar": ["mapa-tematico", "negocio"], "mapa-tematico": ["negocio", "cambios-y-veredictos"],
    "visibilidad": ["negocio", "cambios-y-veredictos"],
}
MAX_LEER = 6000


def _wiki(slug: str) -> Path:
    return C.carpeta(slug) / "wiki"


def _hoy() -> str:
    return time.strftime("%Y-%m-%d")


def _git(w: Path, mensaje: str) -> None:
    if not (w / ".git").exists():
        return
    try:
        subprocess.run(["git", "-C", str(w), "add", "-A"], capture_output=True, timeout=30)
        subprocess.run(["git", "-C", str(w), "-c", "user.name=hermes-seo", "-c", "user.email=hermes-seo@localhost",
                        "commit", "-q", "-m", mensaje], capture_output=True, timeout=30)
    except (OSError, subprocess.SubprocessError):
        pass


def escribir(slug: str, nombre: str, cuerpo: str, fuentes: list | None = None, nota_log: str = "") -> bool:
    """(Re)escribe una página fija con su cabecera, la pone en index.md y apunta en log.md. Nunca lanza."""
    try:
        w = _wiki(slug)
        if not w.is_dir():
            return False
        titulo, tags = PAGINAS[nombre]
        f = w / "concepts" / f"{nombre}.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        creado = _hoy()
        if f.exists():
            m = re.search(r"^created: (\S+)", f.read_text(errors="replace"), re.M)
            creado = m.group(1) if m else creado
        nuevo = (f"---\ntitle: {titulo}\ncreated: {creado}\nupdated: {_hoy()}\ntype: concept\ntags: [{', '.join(tags)}]\n"
                 f"sources: [{', '.join(fuentes or ['hermes-seo'])}]\nconfidence: high\n---\n\n# {titulo}\n\n"
                 f"_Página que escribe hermes-seo sola; no la edites a mano (se regenera)._\n\n{cuerpo.strip()}\n")
        if f.exists() and f.read_text(errors="replace").split("\n---\n", 1)[-1] == nuevo.split("\n---\n", 1)[-1]:
            return True   # sin cambios
        f.write_text(nuevo)
        idx = w / "index.md"
        s = idx.read_text(errors="replace") if idx.exists() else f"# Wiki\n\n## Concepts\n"
        if f"[[{nombre}]]" not in s:
            linea = f"- [[{nombre}]] — {titulo} (la escribe hermes-seo)"
            s = s.replace("## Concepts\n", f"## Concepts\n{linea}\n", 1) if "## Concepts\n" in s else s.rstrip() + f"\n\n## Concepts\n{linea}\n"
            idx.write_text(s)
        with open(w / "log.md", "a") as lg:
            lg.write(f"- {_hoy()} · {nota_log or 'actualizada'} → [[{nombre}]]\n")
        _git(w, f"hermes-seo: {nombre} ({nota_log or 'actualizada'})")
        return True
    except Exception:   # noqa: BLE001 — la memoria nunca frena el sistema
        return False


def _jsonl(p: Path) -> list:
    try:
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


# ── páginas derivadas de los registros (idempotentes) ───────────────────────────────────────────────────────────────
def regenerar_decisiones(slug: str) -> None:
    d = C.carpeta(slug)
    filas = _jsonl(d / "puertas.jsonl")
    dec = [f"- {str(r.get('ts'))[:10]} · {r.get('tipo')} · **{r.get('verbo')}** por {r.get('firma') or r.get('persona')}"
           f"{' (forzada: ' + r['forzado'] + ')' if r.get('forzado') else ''} → {str(r.get('resultado', ''))[:120]}"
           f" (encargo {r.get('encargo') or '—'}, puerta {r.get('puerta')})" for r in filas]
    escribir(slug, "decisiones", "\n".join(dec[-80:]) or "Aún no hay decisiones.", ["puertas.jsonl"], "decisión en una puerta")
    cor = [f"- {str(r.get('ts'))[:10]} · {r.get('tipo')} ({r.get('verbo')}, encargo {r.get('encargo') or '—'}): «{str(r.get('texto')).strip()[:500]}»"
           for r in filas if str(r.get("texto") or "").strip() and r.get("verbo") in ("cambios", "descarto", "rechazo", "ignoro")]
    if cor:
        escribir(slug, "correcciones", "Lo que la persona pidió cambiar o por qué descartó. **Tenlo en cuenta para no repetirlo.**\n\n"
                 + "\n".join(cor[-60:]), ["puertas.jsonl"], "corrección de la persona")


def regenerar_cambios(slug: str) -> None:
    d = C.carpeta(slug)
    l = []
    for r in _jsonl(d / "cambios.jsonl"):
        l.append(f"- {str(r.get('ts'))[:10]} · {r.get('clase') or '?'} · {r.get('url') or ', '.join(r.get('urls') or []) or '—'}"
                 f" · hipótesis: {str(r.get('hipotesis') or '—')[:200]} (cambio {r.get('id')})")
    for t in sorted((d / "tandas").glob("*-veredicto.json")) if (d / "tandas").is_dir() else []:
        v = B.leer(t) or {}
        l.append(f"- {str(v.get('ts', ''))[:10]} · **veredicto de la tanda {v.get('tanda')}: {v.get('salida')}** — {v.get('explicacion', '')[:200]}")
    escribir(slug, "cambios-y-veredictos", "\n".join(l[-80:]) or "Aún no hay cambios publicados.", ["cambios.jsonl", "tandas/"], "cambio o veredicto")


def _mercado(x) -> str:
    if isinstance(x, dict):
        return str(x.get("pais") or x.get("codigo") or x.get("bing") or json.dumps(x, ensure_ascii=False))
    return str(x)


def regenerar_negocio(slug: str) -> None:
    cfg = C.leer(slug)
    n = cfg.get("negocio") or {}
    l = [f"- Web: {cfg.get('nombre')} ({cfg.get('dominio')}), estado {cfg.get('estado_web')}",
         f"- Idioma y mercados: {cfg.get('idioma')} · {', '.join(_mercado(x) for x in cfg.get('mercados') or []) or '—'}"]
    for k, t in (("publico", "Público"), ("voz", "Voz"), ("objetivo", "Objetivo"), ("conversion", "Qué cuenta como conversión"),
                 ("tipo_web", "Tipo de web"), ("restricciones", "Qué no se puede decir"), ("historial", "Historial")):
        if n.get(k):
            l.append(f"- {t}: {n[k] if isinstance(n[k], str) else json.dumps(n[k], ensure_ascii=False)}")
    pol = cfg.get("politicas") or {}
    if pol:
        l.append(f"- Reglas: {json.dumps(pol, ensure_ascii=False)}")
    if cfg.get("competidores"):
        l.append(f"- Competidores: {', '.join(str(c) for c in cfg['competidores'])}")
    escribir(slug, "negocio", "\n".join(l), ["cliente.json"], "configuración de la web")


def de_salida(slug: str, eid: str, memoria: dict) -> None:
    """Fin de una pipeline que declara «memoria»: {pagina, de, seccion?}: copia esa sección de su salida (enlazada)."""
    try:
        f = C.carpeta(slug) / "encargos" / eid / memoria["de"]
        texto = f.read_text(errors="replace")
        sec = memoria.get("seccion")
        if sec:
            m = re.search(rf"^(#+)\s*{re.escape(sec)}.*?$\n(.*?)(?=^\1\s|\Z)", texto, re.M | re.S)
            texto = m.group(2) if m else texto
        cuerpo = f"Sale del encargo `{eid}` ({memoria['de']}). Ver el original para el detalle.\n\n{texto.strip()[:MAX_LEER]}"
        escribir(slug, memoria["pagina"], cuerpo, [f"encargo {eid}"], f"cierre de {eid}")
    except Exception:   # noqa: BLE001
        pass


def para_etapa(slug: str, etapa: str, lee: list | None = None) -> str:
    """Extractos de las páginas que le tocan a una etapa (≤ MAX_LEER). Las páginas-registro, por la cola."""
    w = _wiki(slug) / "concepts"
    partes = []
    for nombre in (lee or LEE.get(etapa) or ["negocio"]):
        f = w / f"{nombre}.md"
        if not f.exists():
            continue
        s = f.read_text(errors="replace").split("\n---\n", 1)[-1].strip()
        s = re.sub(r"^_Página que escribe.*?_\n+", "", re.sub(r"^# .*\n+", "", s), flags=re.S)
        tope = MAX_LEER // max(1, len(lee or LEE.get(etapa) or ["negocio"]))
        partes.append(f"### {PAGINAS.get(nombre, (nombre,))[0]}\n" + (s if len(s) <= tope else "…\n" + s[-tope:]))
    return "\n\n".join(partes)[:MAX_LEER]


def ultimas(slug: str, n: int = 4) -> list:
    try:
        return [l.strip() for l in (_wiki(slug) / "log.md").read_text().splitlines() if l.startswith("- ")][-n:]
    except OSError:
        return []


def sembrar(slug: str) -> list:
    """Primera siembra (idempotente): negocio, mapa de la última estrategia, decisiones, correcciones y cambios."""
    hecho = []
    try:   # el SCHEMA de la web conoce las páginas fijas
        sch = _wiki(slug) / "SCHEMA.md"
        plantilla = (AQUI.parent.parent / "encargado" / "wiki" / "SCHEMA.md").read_text()
        seccion = plantilla[plantilla.index("## Fixed pages"):]
        if sch.exists() and "## Fixed pages" not in sch.read_text():
            sch.write_text(sch.read_text().rstrip() + "\n\n" + seccion)
    except (OSError, ValueError):
        pass
    regenerar_negocio(slug); hecho.append("negocio")
    E = _cargar("hseo_encargos")
    est = [e for e in E.listar(slug) if e.get("pipeline") == "estrategia"]
    if est:
        de_salida(slug, est[-1]["id"], {"pagina": "mapa-tematico", "de": "plan-editorial.md", "seccion": "Mapa temático"})
        hecho.append("mapa-tematico")
    regenerar_decisiones(slug); hecho.append("decisiones/correcciones")
    regenerar_cambios(slug); hecho.append("cambios-y-veredictos")
    return hecho


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["sembrar"] and len(a) == 2:
        print("Sembrado: " + ", ".join(sembrar(a[1])))
    elif a[:1] == ["para"] and len(a) == 3:
        print(para_etapa(a[1], a[2]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
