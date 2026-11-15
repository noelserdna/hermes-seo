"""El encargado de una web: su foto al abrir una sesión y el vigía sin IA (copiado y adaptado de hermes-sdd,
hsdd_proyectos.py foto-encargado / vigia).

  hseo_encargado.py foto <web>     lo que el encargado sabe al abrir una sesión (y marca «visto»)
  hseo_encargado.py vigia <web>    una línea estable por asunto; Hermes solo despierta al modelo si la salida cambia

Asuntos del vigía:
  PARADA | <encargo> | <etapa>: <motivo>          una etapa falló y el encargo está parado
  PUERTA CON ERROR | <puerta> | <error>           el notario no pudo completar lo decidido
  PUERTA ESPERANDO | <puerta> | más de 4 h / 24 h  una decisión lleva tiempo sin tomarse
  DECIDIDA SIN FIRMAR | <puerta> | …              pasó la ventana y el notario no firmó (¿gateway caído?)
  ENCARGO SIN AVANZAR | <encargo> | más de 12 h   en marcha pero ninguna etapa registró nada
  DATOS SIN ACTUALIZAR | <fuente> | más de 3 días la copia de Search Console no se actualiza
  DISCO CASI LLENO | <punto> | más del 85 % / 95 %   se acaba el espacio (worktrees, cachés, datos)
"""
from __future__ import annotations

import importlib.util
import json
import sys
import time
from datetime import datetime, timezone
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
PU = _cargar("hseo_puertas")


def _ts(t) -> float:
    try:
        return datetime.strptime(str(t)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return 0.0


def _jsonl(p: Path) -> list:
    try:
        return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def _tramo(segundos: float, tramos=((86400, "más de 24 h"), (14400, "más de 4 h"))) -> str:
    return next((t for s, t in tramos if segundos >= s), "")


def vigia(slug: str, ahora: float | None = None) -> list:
    ahora = ahora or time.time()
    out = []
    d = C.carpeta(slug)
    etapas = _jsonl(d / "etapas.jsonl")
    for e in E.listar(slug, abiertos=True):
        if e.get("estado") == "parado":
            fallo = next((r for r in reversed(etapas) if r.get("encargo") == e["id"] and r.get("resultado") != "done"), {})
            out.append(f"PARADA | {e['id']} | {fallo.get('etapa', '?')}: {str(fallo.get('motivo', ''))[:120]}")
        elif e.get("estado") == "en-curso":
            ultimo = max([_ts(r["ts"]) for r in etapas if r.get("encargo") == e["id"]] + [_ts(e.get("creado"))])
            t = _tramo(ahora - ultimo, ((86400, "más de 24 h"), (43200, "más de 12 h")))
            if t:
                out.append(f"ENCARGO SIN AVANZAR | {e['id']} | {t}")
    for p in PU.puertas(("abierta", "decidida", "error")):
        if p["cliente"] != slug:
            continue
        if p["estado"] == "error":
            out.append(f"PUERTA CON ERROR | {p['id']} | {str(p.get('error', ''))[:120]}")
        elif p["estado"] == "decidida" and ahora > float(p.get("firmar_en") or 0) + 600:
            out.append(f"DECIDIDA SIN FIRMAR | {p['id']} | {p['titulo'][:80]}")
        # una puerta abierta no es un asunto: no hay recordatorios (sale en el parte y en /seo_puertas)
    if "gsc" in C.capacidades(C.leer(slug)):
        fotos = sorted((d / "datos" / "gsc").glob("*.json")) if (d / "datos" / "gsc").is_dir() else []
        if fotos:
            t = _tramo(ahora - fotos[-1].stat().st_mtime, ((7 * 86400, "más de 7 días"), (3 * 86400, "más de 3 días")))
            if t:
                out.append(f"DATOS SIN ACTUALIZAR | search-console | {t}")
    for x in B.disco():
        if x["aviso"]:
            out.append(f"DISCO CASI LLENO | {x['punto']} | {'más del 95 %' if x['usado_pct'] >= 95 else 'más del 85 %'}")
    return out


def foto(slug: str, marcar: bool = True) -> str:
    """Contexto de la web + en qué punto está + lo que pasó desde la última sesión del encargado."""
    contexto = _cargar("hseo_etapa").contexto(slug)
    estado = _cargar("hseo_cli").estado(slug)
    d = C.carpeta(slug)
    visto_f = B.home() / "encargados" / f"{slug}.visto"
    visto = _ts(visto_f.read_text().strip()) if visto_f.exists() else 0
    nuevas = []
    for r in _jsonl(d / "puertas.jsonl"):
        if _ts(r.get("ts")) > visto:
            nuevas.append(f"- 🚪 {r.get('tipo')}: {r.get('verbo')} por {r.get('firma')} → {r.get('resultado')}")
    for r in _jsonl(d / "etapas.jsonl"):
        if _ts(r.get("ts")) > visto and r.get("resultado") != "done":
            nuevas.append(f"- ⚠️ {r.get('etapa')} ({r.get('encargo')}): {r.get('resultado')} — {str(r.get('motivo', ''))[:100]}")
    hechas = sum(1 for r in _jsonl(d / "etapas.jsonl") if _ts(r.get("ts")) > visto and r.get("resultado") == "done")
    if hechas:
        nuevas.append(f"- ✅ {hechas} etapa(s) terminadas")
    asuntos = vigia(slug)
    partes = [contexto, "## En qué punto está", estado]
    if asuntos:
        partes += ["## Asuntos del vigía", *[f"- {a}" for a in asuntos]]
    partes += ["## Desde tu última sesión", *(nuevas[-15:] or ["- Nada nuevo."])]
    if marcar:
        visto_f.parent.mkdir(parents=True, exist_ok=True)
        visto_f.write_text(B.ahora() + "\n")
    return "\n".join(partes)


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if len(a) != 2 or a[0] not in ("foto", "vigia"):
        print(__doc__, file=sys.stderr)
        return 2
    try:
        print(foto(a[1]) if a[0] == "foto" else "\n".join(vigia(a[1])))
    except B.Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
