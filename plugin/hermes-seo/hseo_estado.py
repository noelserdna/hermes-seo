"""El estado REAL de una web (o de la cartera) en cada turno de conversación, sin modelo.

Lo inyecta el plugin con el hook pre_llm_call en la conversación del encargado (su web) y de la coordinadora (todas):
puertas abiertas con fecha y edad, encargos en marcha, incidencias vivas, lo que pasó en los últimos 7 días, el
titular del último informe de cada tipo y el último parte con sus propuestas. Corto (≈1.500 caracteres por web) y
recalculado en cada turno: no envejece como la foto del prompt, que se congela al abrir la sesión.

  hseo_estado.py turno <web>    ·    hseo_estado.py cartera
"""
from __future__ import annotations

import importlib.util
import json
import re
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

MAX_WEB = 1500
DIAS_RECIENTE = 7
# lo que parezca una clave no entra nunca en el contexto (puede venir de un informe que copió una salida)
_CLAVE = re.compile(r"(sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abp]-[A-Za-z0-9-]{10,}|"
                    r"AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}|[A-Za-z0-9+/_-]{40,})")


def tapar(texto: str) -> str:
    return _CLAVE.sub("[clave tapada]", texto)


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


def _edad(segundos: float) -> str:
    h = segundos / 3600
    return f"{int(h)} h" if h < 48 else f"{int(h // 24)} días"


def _titular(d: Path, salida: str | None) -> str:
    """Primera línea con contenido del informe (sin marcas de título)."""
    if not salida or not (d / salida).exists():
        return ""
    try:
        for l in (d / salida).read_text(errors="replace").splitlines():
            l = l.strip().lstrip("#").strip()
            if l and not l.startswith(("---", "VEREDICTO")):
                return l[:140]
    except OSError:
        pass
    return ""


def turno(slug: str, ahora: float | None = None) -> str:
    ahora = ahora or time.time()
    cfg = C.leer(slug)
    d = C.carpeta(slug)
    lineas = [f"## Estado real de {cfg.get('nombre') or slug} ({datetime.now().strftime('%d-%m %H:%M')}, se recalcula en cada turno)"]

    puertas = [p for p in PU.puertas(("abierta", "decidida", "error")) if p.get("cliente") == slug]
    if puertas:
        lineas.append("Puertas pendientes:")
        for p in sorted(puertas, key=lambda x: x.get("creada", "")):
            extra = " · ⛔ aviso grave: no se puede aprobar" if PU.graves(p) else ""
            lineas.append(f"- {p['titulo'][:70]} ({p['estado']}, desde {str(p.get('creada', ''))[:10]}, "
                          f"hace {_edad(ahora - _ts(p.get('creada')))}){extra} [{p['id']}]")
    else:
        lineas.append("Puertas pendientes: ninguna.")

    abiertos = [e for e in E.listar(slug, abiertos=True) if e.get("estado") != "en-puerta"]
    if abiertos:
        lineas.append("En marcha:")
        for e in abiertos[-6:]:
            lineas.append(f"- {e.get('nombre', '')} · {e.get('estado')} · desde {str(e.get('creado', ''))[:10]} [{e['id']}]")

    inc = [B.leer(f) or {} for f in sorted((d / "incidencias").glob("*.json"))] if (d / "incidencias").is_dir() else []
    vivas = [i for i in inc if i.get("estado") in ("viva", "avisada")]
    if vivas:
        lineas.append("Incidencias vivas: " + "; ".join(f"{i.get('texto', '')[:80]} ({i.get('estado')})" for i in vivas[:4]))

    desde = ahora - DIAS_RECIENTE * 86400
    hechos = []
    for r in _jsonl(d / "puertas.jsonl"):
        if _ts(r.get("ts")) >= desde:
            hechos.append(f"{str(r.get('ts'))[:10]} puerta {r.get('tipo')}: {r.get('verbo')} → {str(r.get('resultado', ''))[:60]}")
    for r in _jsonl(d / "cambios.jsonl"):
        if _ts(r.get("ts")) >= desde:
            hechos.append(f"{str(r.get('ts'))[:10]} publicado: {r.get('url') or r.get('clase', '')}")
    if hechos:
        lineas.append(f"Últimos {DIAS_RECIENTE} días:")
        lineas += [f"- {h}" for h in hechos[-6:]]

    # el último informe de cada tipo (aunque tenga más de 7 días): lo que se sabe, con su fecha
    ultimos: dict = {}
    for e in E.listar(slug):
        if e.get("informe") and e.get("estado") == "hecho":
            ultimos[e.get("pipeline")] = e
    if ultimos:
        lineas.append("Último informe de cada tipo:")
        for pid, e in sorted(ultimos.items(), key=lambda kv: kv[1].get("creado", ""), reverse=True)[:6]:
            de = E.carpeta(slug, e["id"])
            salida = None
            try:
                etapas = _cargar("hseo_pipelines").cargar(pid, slug)["etapas"]
                salida = next((s.get("salida") for s in reversed(etapas) if s.get("salida")), None)
            except Exception:   # noqa: BLE001 — una pipeline que ya no existe no rompe el estado
                pass
            tit = _titular(de, salida)
            lineas.append(f"- {e.get('nombre')} ({str(e.get('creado', ''))[:10]}): {tit or 'ver ' + str(de / (salida or ''))}")

    parte = B.leer(d / "informes" / "partes" / "ultimo.json")
    if isinstance(parte, dict) and parte.get("propuestas"):
        lineas.append(f"Propuestas del parte del {parte.get('fecha', '?')} (la persona responde «haz la N»):")
        lineas += [f"{i}. {p.get('texto', '')[:110]}" for i, p in enumerate(parte["propuestas"], 1)]

    at = B.leer(d / "aterrizaje.json")
    if isinstance(at, dict) and at.get("pasos"):
        hechos_at = sum(1 for p in at["pasos"].values() if p.get("ok"))
        lineas.append(f"Aterrizaje: {hechos_at} de {len(at['pasos'])} pasos.")

    texto = tapar("\n".join(lineas))
    return texto if len(texto) <= MAX_WEB else texto[:MAX_WEB - 20] + "\n… (recortado)"


def cartera(ahora: float | None = None) -> str:
    lineas = [f"## Estado real de la cartera ({datetime.now().strftime('%d-%m %H:%M')})", B.disco_linea()]
    lat = B.leer(B.home() / "latido.json")
    if isinstance(lat, dict) and lat.get("ts"):
        lineas.append(f"Bucle de puertas: último latido {str(lat.get('ts'))[:16]}")
    cop = B.leer(B.home() / "copia.json")
    if isinstance(cop, dict):
        lineas.append(f"Copia: {'bien' if cop.get('ok') else 'FALLÓ: ' + str(cop.get('motivo', ''))[:80]} ({str(cop.get('ts', ''))[:16]})")
    for slug in C.listar():
        try:
            cfg = C.leer(slug)
        except B.Rechazo:
            continue
        ps = [p for p in PU.puertas(("abierta", "decidida", "error")) if p.get("cliente") == slug]
        marcha = [e for e in E.listar(slug, abiertos=True) if e.get("estado") != "en-puerta"]
        r = {}
        try:
            r = _cargar("hseo_datos").resumen(slug, 28)
        except Exception:   # noqa: BLE001
            pass
        cifra = f"{r['actual']['clics']} clics / {r['actual']['impresiones']} impr. en 28 días" if r.get("hay_datos") else "sin datos"
        lineas.append(f"- {cfg.get('nombre') or slug}: {len(ps)} puerta(s), {len(marcha)} en marcha, {cifra}")
    lineas.append("Para el detalle de una web: hseo estado <web> · hseo preguntar <web> \"…\"")
    return tapar("\n".join(lineas))[:3000]


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["turno"] and len(a) == 2:
        print(turno(a[1]))
    elif a[:1] == ["cartera"]:
        print(cartera())
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
