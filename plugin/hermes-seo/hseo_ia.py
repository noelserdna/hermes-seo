"""Resumen de visibilidad en IA, sin modelo: de las salidas de chatgpt-busca, claude-busca y brave-busca de una ronda
(datos/ia/<motor>-<fecha>.json), qué parte de las respuestas CITA la web (enlace) y cuál la MENCIONA (nombre o dominio
en el texto), por motor, con un intervalo de confianza de Wilson; y qué competidores salen y cuánto. Solo dice que algo
cambió si los intervalos de dos rondas no se solapan (con 30 respuestas, casi todo es ruido).

  hseo_ia.py resumen <web> [--fecha AAAA-MM-DD]   → datos/ia/resumen-<fecha>.json (lo usa la skill y el parte)
"""
from __future__ import annotations

import importlib.util
import json
import math
import re
import sys
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


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if not n:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return round(max(0.0, (c - m) / d), 3), round(min(1.0, (c + m) / d), 3)


def _rondas(slug: str) -> dict:
    """{fecha: {motor: fichero}} con las salidas de las herramientas."""
    out: dict = {}
    for f in sorted((C.carpeta(slug) / "datos" / "ia").glob("*.json")):
        m = re.match(r"^(?:decision-)?(\d{4}-\d{2}-\d{2})?-?(chatgpt|claude|brave)(?:-(\d{4}-\d{2}-\d{2}))?$", f.stem) or \
            re.match(r"^(chatgpt|claude|brave)-(\d{4}-\d{2}-\d{2})$", f.stem)
        if not m:
            continue
        g = [x for x in m.groups() if x]
        motor = next(x for x in g if x in ("chatgpt", "claude", "brave"))
        fecha = next((x for x in g if re.fullmatch(r"\d{4}-\d{2}-\d{2}", x)), "")
        if fecha:
            out.setdefault(fecha, {})[motor] = f
    return out


def resumen(slug: str, fecha: str | None = None) -> dict:
    cfg = C.leer(slug)
    dom = str(cfg.get("dominio") or "").lower()
    marca = [t.lower() for t in (cfg.get("marca") or [dom.split(".")[0], str(cfg.get("nombre") or "")]) if t]
    competidores = [str(c).lower() for c in ((cfg.get("ia") or {}).get("competidores") or cfg.get("competidores") or [])]
    rondas = _rondas(slug)
    if not rondas:
        return {"hay_datos": False}
    fecha = fecha or max(rondas)
    motores = {}
    for motor, f in sorted(rondas.get(fecha, {}).items()):
        d = B.leer(f) or {}
        filas = d.get("filas") or d.get("preguntas") or []
        n = cita = menciona = 0
        comp = {c: 0 for c in competidores}
        for r in filas:
            urls = [u for u in (r.get("citas") or r.get("top10") or []) if isinstance(u, str)]
            texto = str(r.get("respuesta") or "").lower()
            if "error" in r or (not urls and not texto):
                continue
            n += 1
            c = any(dom in u.lower() for u in urls) or (r.get("puesto") is not None)
            cita += c
            menciona += c or any(t and t in texto for t in marca)
            for k in comp:
                comp[k] += any(k in u.lower() for u in urls) or k in texto
        lo, hi = wilson(cita, n)
        motores[motor] = {"respuestas": n, "cita": cita, "menciona": menciona, "cita_pct": round(cita / n * 100, 1) if n else 0,
                          "intervalo_cita": [lo, hi], "competidores": {k: v for k, v in comp.items() if v}}
    anteriores = sorted(f for f in rondas if f < fecha)
    cambios = {}
    if anteriores:
        prev = resumen(slug, anteriores[-1]) if anteriores[-1] != fecha else {}
        for motor, v in motores.items():
            p = (prev.get("motores") or {}).get(motor)
            if p and p["respuestas"]:
                a, b = p["intervalo_cita"], v["intervalo_cita"]
                cambios[motor] = "sube" if b[0] > a[1] else ("baja" if b[1] < a[0] else "sin cambio que se pueda afirmar")
    r = {"hay_datos": True, "fecha": fecha, "motores": motores, "frente_a": anteriores[-1] if anteriores else None, "cambios": cambios}
    return r


def guardar(slug: str, fecha: str | None = None) -> dict:
    r = resumen(slug, fecha)
    if r.get("hay_datos"):
        B.escribir(C.carpeta(slug) / "datos" / "ia" / f"resumen-{r['fecha']}.json", r)
    return r


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["resumen"] and len(a) >= 2:
        f = a[a.index("--fecha") + 1] if "--fecha" in a else None
        print(json.dumps(guardar(a[1], f), ensure_ascii=False, indent=1))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
