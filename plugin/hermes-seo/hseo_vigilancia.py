"""Vigilancia de una web, sin modelo: detecta incidencias, intenta UN arreglo y solo avisa si no se arregla.

Lo lanza un cron --no-agent cada 5 min en el perfil del encargado; su salida es el aviso (vacía = silencio).

  hseo_vigilancia.py ciclo <web>               detecta, intenta, avisa (lo que imprime llega a la persona)
  hseo_vigilancia.py arreglar <web> <firma>    el intento de arreglo (lo lanza ciclo, desacoplado)
  hseo_vigilancia.py ver <web>                 las incidencias y su estado

Cada incidencia vive en clientes/<web>/incidencias/<firma>.json (firma = clase + recurso):
  viva → (intentando → ) avisada → resuelta.   Lo resuelto sale como una línea en el parte, no como mensaje.
Lo que es del servidor (disco, copia, servicios) no es de una web: lo vigila el sistema (latido/sistema.sh).
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import time
from datetime import timedelta
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
ES = _cargar("hseo_estado")
ESPERA_ARREGLO = 15 * 60   # tras el intento, cuánto se espera antes de avisar si sigue


def _dir(slug: str) -> Path:
    return C.carpeta(slug) / "incidencias"


def _firma(clase: str, recurso: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", f"{clase}-{recurso}".lower()).strip("-")[:90]


def _caida_clics(slug: str) -> str:
    """Dos semanas seguidas por debajo del 60 % de la media de las 4 anteriores (con ≥30 clics/semana de media)."""
    try:
        D = _cargar("hseo_datos")
        con = D._db(slug)
        fin = D._ultimo(con)
        if not fin:
            con.close()
            return ""
        semanas = []
        for i in range(6):
            b = fin - timedelta(days=7 * i)
            a = b - timedelta(days=6)
            semanas.append(D._suma(con, a.isoformat(), b.isoformat())["clics"])
        con.close()
    except Exception:   # noqa: BLE001
        return ""
    recientes, previas = semanas[:2], semanas[2:]
    media = sum(previas) / len(previas)
    if media >= 30 and all(s < 0.6 * media for s in recientes):
        return f"los clics de las dos últimas semanas ({recientes[1]} y {recientes[0]}) están por debajo del 60 % de la media de las 4 anteriores ({media:.0f})"
    return ""


def detectar(slug: str, ahora: float | None = None) -> list:
    ahora = ahora or time.time()
    d = C.carpeta(slug)
    out = []
    etapas = ES._jsonl(d / "etapas.jsonl")
    for e in E.listar(slug, abiertos=True):
        if e.get("estado") == "parado":
            fallo = next((r for r in reversed(etapas) if r.get("encargo") == e["id"] and r.get("resultado") not in ("done", "cambios")), {})
            out.append({"clase": "parada", "recurso": e["id"], "arreglo": "reintentar",
                        "datos": {"encargo": e["id"], "etapa": fallo.get("etapa")},
                        "texto": f"«{e.get('nombre')}» está parado en {fallo.get('etapa', '?')}: {str(fallo.get('motivo', ''))[:120]}"})
        elif e.get("estado") == "en-curso":
            ultimo = max([ES._ts(r["ts"]) for r in etapas if r.get("encargo") == e["id"]] + [ES._ts(e.get("creado"))])
            if ahora - ultimo > 12 * 3600:
                out.append({"clase": "sin-avanzar", "recurso": e["id"], "arreglo": None,
                            "texto": f"«{e.get('nombre')}» no avanza desde hace {ES._edad(ahora - ultimo)}"})
    for p in PU.puertas(("decidida", "error")):
        if p.get("cliente") != slug:
            continue
        if p["estado"] == "error":
            out.append({"clase": "puerta-error", "recurso": p["id"], "arreglo": None,
                        "texto": f"la puerta «{p['titulo'][:60]}» no se pudo completar: {str(p.get('error', ''))[:120]}"})
        elif ahora > float(p.get("firmar_en") or 0) + 600:
            out.append({"clase": "sin-firmar", "recurso": p["id"], "arreglo": "firmar",
                        "texto": f"la puerta «{p['titulo'][:60]}» está decidida pero sin ejecutar"})
    caps = C.capacidades(C.leer(slug))
    if "gsc" in caps:
        rec = ES._jsonl(d / "datos" / "recogidas.jsonl")
        ultima = rec[-1] if rec else {}
        caducado = next((f for f in ultima.get("fallos") or [] if "caducado" in f or "reconectar" in f), "")
        if caducado:
            out.append({"clase": "acceso", "recurso": "search-console", "arreglo": "recoger",
                        "texto": "el acceso a Search Console ha caducado", "mano": "reconectar Search Console (hermes -p seo-analista mcp login seo)"})
        fotos = sorted((d / "datos" / "gsc").glob("*.json")) if (d / "datos" / "gsc").is_dir() else []
        if fotos and ahora - fotos[-1].stat().st_mtime > 3 * 86400 and not caducado:
            out.append({"clase": "datos", "recurso": "search-console", "arreglo": "recoger",
                        "texto": f"los datos de Search Console no se actualizan desde hace {ES._edad(ahora - fotos[-1].stat().st_mtime)}"})
        caida = _caida_clics(slug)
        if caida:
            out.append({"clase": "caida-clics", "recurso": "google", "arreglo": None, "texto": caida})
    for x in out:
        x["firma"] = _firma(x["clase"], x["recurso"])
    return out


DESCRIBE = {"reintentar": "reintenté la etapa", "firmar": "volví a intentar ejecutarla",
            "recoger": "volví a recoger los datos (y a renovar el acceso)"}


def ciclo(slug: str, ahora: float | None = None, lanzar=None) -> list:
    """Devuelve las líneas de aviso (vacía = nada que contar). `lanzar(slug, firma)` lanza el arreglo (desacoplado)."""
    ahora = ahora or time.time()
    lanzar = lanzar or _lanzar_arreglo
    dd = _dir(slug)
    dd.mkdir(parents=True, exist_ok=True)
    detectadas = {x["firma"]: x for x in detectar(slug, ahora)}
    avisos = []
    for firma, x in detectadas.items():
        f = dd / f"{firma}.json"
        inc = B.leer(f) or {}
        if not inc or inc.get("estado") == "resuelta":
            inc = {**x, "estado": "viva", "creada": B.ahora(), "intentos": 0}
        inc["texto"] = x["texto"]
        if inc["estado"] == "viva":
            if x.get("arreglo") and inc.get("intentos", 0) == 0:
                inc.update(estado="intentando", intentos=1, intento_ts=ahora)
                B.escribir(f, inc)
                lanzar(slug, firma)
                continue
            inc["estado"] = "avisada"
            avisos.append(_aviso(inc))
        elif inc["estado"] == "intentando" and ahora - float(inc.get("intento_ts") or 0) > ESPERA_ARREGLO:
            inc["estado"] = "avisada"
            avisos.append(_aviso(inc))
        B.escribir(f, inc)
    for f in dd.glob("*.json"):
        inc = B.leer(f) or {}
        if inc.get("estado") in ("viva", "intentando", "avisada") and f.stem not in detectadas:
            inc.update(estado="resuelta", resuelta=B.ahora(), sola=inc.get("estado") != "avisada")
            B.escribir(f, inc)
    B.escribir(C.carpeta(slug) / "vigilancia.json", {"ts": B.ahora(), "vivas": len(detectadas)})
    return avisos


def _aviso(inc: dict) -> str:
    l = f"⚠️ {inc['texto']}."
    if inc.get("intentos"):
        l += f" Ya {DESCRIBE.get(inc.get('arreglo'), 'lo intenté')}" + (f" ({inc['probado']})" if inc.get("probado") else "") + " y sigue igual."
    if inc.get("mano"):
        l += f" Hace falta tu mano: {inc['mano']}."
    return l


def _lanzar_arreglo(slug: str, firma: str) -> None:
    log = C.carpeta(slug) / "logs" / f"arreglo-{firma}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(B.desacoplar([sys.executable, str(Path(__file__)), "arreglar", slug, firma]), start_new_session=True,
                     stdout=open(log, "w"), stderr=subprocess.STDOUT)


def arreglar(slug: str, firma: str) -> str:
    f = _dir(slug) / f"{firma}.json"
    inc = B.leer(f) or {}
    a, datos = inc.get("arreglo"), inc.get("datos") or {}
    try:
        if a == "reintentar":
            _cargar("hseo_cli").reintentar(slug, datos["encargo"], datos.get("etapa") or E.leer(slug, datos["encargo"])["etapas"][-1]["id"])
            r = "reintentada"
        elif a == "firmar":
            r = "; ".join(f"{g}: {'ok' if ok_ else m}" for g, ok_, m in PU.vencidas()) or "nada que firmar"
        elif a == "recoger":
            fallos = _cargar("hseo_datos").recoger(slug)
            r = "sin fallos" if not fallos else "; ".join(fallos)[:200]
        else:
            r = "sin arreglo automático"
    except Exception as e:   # noqa: BLE001
        r = f"falló: {str(e)[:200]}"
    inc = B.leer(f) or inc
    inc["probado"] = r
    B.escribir(f, inc)
    return r


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if a[:1] == ["ciclo"] and len(a) == 2:
        for l in ciclo(a[1]):
            print(l)
    elif a[:1] == ["arreglar"] and len(a) == 3:
        print(arreglar(a[1], a[2]))
    elif a[:1] == ["ver"] and len(a) == 2:
        for f in sorted(_dir(a[1]).glob("*.json")):
            i = B.leer(f) or {}
            print(f"{i.get('estado', '?'):10} {f.stem}: {i.get('texto', '')}")
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
