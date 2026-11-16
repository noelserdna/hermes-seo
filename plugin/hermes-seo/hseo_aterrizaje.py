"""Aterrizaje guiado de una web nueva: 10 pasos que se COMPRUEBAN solos (nunca se dan por hechos porque alguien lo diga),
cada uno enciende su parte del sistema, y ninguna tarea programada arranca hasta que su acceso está comprobado.

  hseo_aterrizaje.py empezar <web>      crea la lista (las webs que ya existían quedan como «legado»: no se les apaga nada)
  hseo_aterrizaje.py comprobar <web>    vuelve a comprobar los pasos (y con los mínimos lanza la línea base, una vez)
  hseo_aterrizaje.py ver <web>          la lista («n de 10» y el siguiente paso)
  hseo_aterrizaje.py omitir <web> <n>   solo los pasos 6, 7 y 8 (Bing, analítica, competidores), y lo hace la coordinadora

Mínimos para empezar a trabajar: 1 (negocio), 2 (idiomas y países), 3 (cómo se publica) y 5 (Search Console).
Al cerrarse la línea base se lanza la estrategia (una vez). Estado: clientes/<web>/aterrizaje.json.
Las claves nunca se escriben en el chat ni en el correo: van en secretos.env (hseo secreto guardar, desde la terminal).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.request
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
Rechazo = B.Rechazo
MINIMOS = (1, 2, 3, 5)
OMITIBLES = (6, 7, 8)


def _get(url: str) -> int:
    if os.environ.get("HSEO_SIN_RED"):
        return 0
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "hermes-seo/0.1 (aterrizaje)"}), timeout=15)
        return r.status
    except Exception:   # noqa: BLE001
        return 0


def _p1(slug, cfg):
    n = cfg.get("negocio") or {}
    falta = [k for k in ("publico", "objetivo", "conversion") if not str(n.get(k) or "").strip()]
    return (not falta, "falta: " + ", ".join(falta) if falta else "público, objetivo y conversión")


def _confirmado(slug: str, claves: tuple) -> bool:
    """¿Alguien ha puesto (o confirmado) estas claves? Lo que trae la plantilla no cuenta como dicho."""
    for r in _jsonl(C.carpeta(slug) / "config.jsonl"):
        if r.get("accion") == "config" and str(r.get("clave") or "").split(".")[0] in claves:
            return True
    return False


def _jsonl(f: Path) -> list:
    out = []
    try:
        for l in f.read_text().splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                continue
    except OSError:
        pass
    return out


def _p2(slug, cfg):
    if not (cfg.get("idioma") and cfg.get("mercados")):
        return False, "faltan el idioma o los mercados"
    if not _confirmado(slug, ("idioma", "mercados")):
        return False, "idioma y mercados son los de la plantilla: confírmalos (hseo config <web> mercados …)"
    return True, "idioma y mercados"


def _p3(slug, cfg):
    pub = (cfg.get("capacidades") or {}).get("publicacion") or {}
    a = pub.get("adaptador")
    if a == "repo-pr":
        repo = Path(os.path.expanduser(str(pub.get("repo") or "")))
        return (repo / ".git").exists(), f"repositorio {'accesible' if (repo / '.git').exists() else 'no encontrado: ' + str(repo)}"
    if a == "wordpress":
        code = _get(str(pub.get("url_api") or ""))
        ok = code == 200 and bool(C.secretos(slug).get("WP_APP_PASSWORD"))
        return ok, "WordPress con contraseña de aplicación" if ok else "falta el acceso a WordPress (URL de la API y contraseña de aplicación)"
    if a == "entrega":
        return True, "entrega a mano"
    if a == "mcp":   # su propio servidor MCP: cuenta cuando el acceso está aprobado
        ok = (C.carpeta(slug) / "mcp-tokens" / "sesion.json").exists()
        return ok, "servidor MCP conectado" if ok else "falta aprobar el acceso al servidor MCP de la web (hseo mcp conectar)"
    return False, "falta decir cómo se publica (repositorio, WordPress, su servidor MCP o entrega a mano)"


def _p4(slug, cfg):
    dom = str(cfg.get("dominio") or "")
    r, s = _get(f"https://{dom}/robots.txt"), _get(f"https://{dom}/sitemap.xml") or _get(f"https://{dom}/sitemap-index.xml")
    return r == 200 and s == 200, f"robots {r or '—'} · sitemap {s or '—'}"


def _p5(slug, cfg):
    fotos = list((C.carpeta(slug) / "datos" / "gsc").glob("*.json")) if (C.carpeta(slug) / "datos" / "gsc").is_dir() else []
    ok = "gsc" in C.capacidades(cfg) and bool(fotos)
    return ok, f"{len(fotos)} días guardados" if ok else "falta dar acceso a Search Console (y que llegue la primera recogida)"


def _p6(slug, cfg):
    ok = "bing" in C.capacidades(cfg)
    return ok, "Bing conectado" if ok else "falta la clave de Bing Webmaster"


def _p7(slug, cfg):
    ok = any(c.startswith("analitica") for c in C.capacidades(cfg))
    return ok, "analítica conectada" if ok else "falta la analítica (Cloudflare, GA4, Plausible) o decir que no hay"


def _p8(slug, cfg):
    comp = bool(cfg.get("competidores"))
    preg = (C.carpeta(slug) / "preguntas-decision.md").exists()
    return comp and preg, f"competidores {'sí' if comp else 'no'} · preguntas para la IA {'sí' if preg else 'no'}"


def _p9(slug, cfg):
    PU = _cargar("hseo_puertas")
    quien = [k for k in (B.leer(B.home() / "aprobadores.json", {}) or {}) if PU.puede_decidir(k, slug)]
    if not (quien and isinstance(cfg.get("politicas"), dict)):
        return False, "falta quién decide las puertas de esta web"
    if not _confirmado(slug, ("politicas",)):
        return False, "el ritmo (políticas) es el de la plantilla: confírmalo (hseo config <web> politicas …)"
    return True, f"deciden: {', '.join(quien)}"


def _p10(slug, cfg):
    c = cfg.get("contacto") or {}
    if (c.get("canal") or "telegram") == "telegram":
        ok = bool((cfg.get("telegram") or {}).get("thread_id"))
        return ok, "por Telegram" if ok else "falta el tema de Telegram"
    ok = bool(c.get("verificado"))
    return ok, f"correo {c.get('correo')} {'comprobado' if ok else 'sin comprobar (responde al correo de confirmación)'}"


PASOS = [
    (1, "Qué es la web, a quién va y qué cuenta como conversión", _p1, "todo lo que se redacta"),
    (2, "Idiomas y países", _p2, "demanda y visibilidad por mercado"),
    (3, "Cómo se publica", _p3, "la puerta de publicar"),
    (4, "Sitemap, robots y aviso a buscadores", _p4, "auditoría y vigilancia"),
    (5, "Search Console", _p5, "datos diarios, métricas y propuestas"),
    (6, "Bing", _p6, "demanda de búsqueda y enlaces"),
    (7, "Analítica", _p7, "visitas y altas"),
    (8, "Competidores y preguntas para la IA", _p8, "radar, visibilidad en IA y autoridad"),
    (9, "Reglas: ritmo y quién decide", _p9, "topes y puertas"),
    (10, "Correo o tema de contacto, comprobado", _p10, "el parte y las puertas"),
]
REQUISITO = {"datos": 5, "metricas-semanales": 5, "revision-mensual": 5, "parte": 1, "radar": 8, "visibilidad-ia": 8,
             "autoridad": 8, "colaboraciones": 8, "usos-candidatos": 8}


def _f(slug: str) -> Path:
    return C.carpeta(slug) / "aterrizaje.json"


def estado(slug: str) -> dict | None:
    return B.leer(_f(slug))


def empezar(slug: str) -> dict:
    e = estado(slug) or {"creado": B.ahora(), "pasos": {}, "lanzados": {}}
    B.escribir(_f(slug), e)
    return comprobar(slug)


def comprobar(slug: str) -> dict:
    e = estado(slug)
    if not e:
        raise Rechazo(f"{slug} no tiene aterrizaje (hseo aterrizaje empezar {slug})")
    cfg = C.leer(slug)
    for n, titulo, f, enciende in PASOS:
        previo = e["pasos"].get(str(n)) or {}
        if previo.get("omitido"):
            continue
        try:
            ok, det = f(slug, cfg)
        except Exception as x:   # noqa: BLE001
            ok, det = False, f"no se pudo comprobar: {str(x)[:100]}"
        e["pasos"][str(n)] = {"ok": ok, "detalle": det, "ts": B.ahora(), **({"desde": previo.get("desde") or B.ahora()} if ok else {})}
    E = _cargar("hseo_encargos")
    hechos = {int(k) for k, v in e["pasos"].items() if v.get("ok") or v.get("omitido")}
    if all(m in hechos for m in MINIMOS) and not e["lanzados"].get("linea-base"):
        try:
            e["lanzados"]["linea-base"] = E.lanzar(slug, "linea-base", quien="aterrizaje")["id"]
        except Rechazo as x:
            e["lanzados"]["linea-base-error"] = str(x)[:200]
    lb = e["lanzados"].get("linea-base")
    if lb and not e["lanzados"].get("estrategia"):
        try:
            if E.leer(slug, lb).get("estado") in ("hecho", "cerrado"):
                e["lanzados"]["estrategia"] = E.lanzar(slug, "estrategia", quien="aterrizaje")["id"]
        except Rechazo:
            pass
    e["completo"] = len(hechos) == len(PASOS)
    B.escribir(_f(slug), e)
    return e


def omitir(slug: str, n: int) -> dict:
    if n not in OMITIBLES:
        raise Rechazo(f"Solo se pueden omitir los pasos {', '.join(map(str, OMITIBLES))}")
    e = estado(slug) or empezar(slug)
    e["pasos"][str(n)] = {"ok": False, "omitido": True, "ts": B.ahora(), "detalle": "omitido"}
    B.escribir(_f(slug), e)
    return comprobar(slug)


def vista(slug: str) -> str:
    e = estado(slug)
    if not e:
        return ""
    cfg = C.leer(slug)
    hechos = sum(1 for v in e["pasos"].values() if v.get("ok") or v.get("omitido"))
    l = [f"🛬 Aterrizaje de {cfg.get('nombre') or slug} · {hechos} de {len(PASOS)}"]
    siguiente = None
    for n, titulo, _, enciende in PASOS:
        v = e["pasos"].get(str(n)) or {}
        marca = "✅" if v.get("ok") else ("➖" if v.get("omitido") else "⬜")
        l.append(f"{marca} {n}. {titulo}" + ("" if v.get("ok") or v.get("omitido") else f" — {v.get('detalle', '')}"))
        if not siguiente and not (v.get("ok") or v.get("omitido")):
            siguiente = (n, titulo, enciende)
    if siguiente:
        l.append(f"\nSiguiente: {siguiente[1]} (enciende: {siguiente[2]}).")
    else:
        l.append("\nTodo listo: la web funciona sola.")
    return "\n".join(l)


def permitido(slug: str, cron: str) -> bool:
    """¿Puede arrancar esta tarea programada? Las webs sin aterrizaje (legado) siempre; las demás, con su paso hecho."""
    e = estado(slug)
    if not e or cron not in REQUISITO:
        return True
    v = e["pasos"].get(str(REQUISITO[cron])) or {}
    return bool(v.get("ok") or v.get("omitido"))


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    try:
        if a[:1] == ["empezar"] and len(a) == 2:
            empezar(a[1]); print(vista(a[1]))
        elif a[:1] == ["comprobar"] and len(a) == 2:
            comprobar(a[1]); print(vista(a[1]))
        elif a[:1] == ["ver"] and len(a) == 2:
            print(vista(a[1]) or f"{a[1]} no tiene aterrizaje (es una web que ya existía)")
        elif a[:1] == ["omitir"] and len(a) == 3:
            omitir(a[1], int(a[2])); print(vista(a[1]))
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
