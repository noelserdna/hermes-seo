"""Tareas periódicas de cada web: qué pipelines se lanzan solas y cuándo, y la recogida diaria de datos.

Por defecto (en la zona horaria de la web), solo las que su configuración permite:
  datos               todos los días 06:00   recoge Search Console, Bing, analítica… (sin IA)
  parte               lunes 10:30            el parte semanal (sin IA): su salida es el mensaje
  vigilancia          cada 5 min             incidencias de la web (sin IA): un intento de arreglo; avisa solo si sigue
  radar               lunes 07:30
  metricas-semanales  lunes 08:00
  revision-mensual    día 1, 08:30
  autoridad           día 2, 10:00           dónde estar para ganar autoridad (abre una puerta con ≤4 gestiones)
  visibilidad-ia      día 1, 09:00           (mensual; tiene coste de APIs: desactivada salvo que la web la active)

cliente.json → crons: {"radar": "0 9 * * 3", "visibilidad-ia": "0 9 1 * *", "metricas-semanales": null}
  (un horario cron la activa o la cambia; null la desactiva)

  hseo_crons.py plan <web>      → JSON [{nombre, horario, orden}]  (lo usa encargado.sh crons)
"""
from __future__ import annotations

import importlib.util
import json
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
PL = _cargar("hseo_pipelines")

DEFECTO = {"datos": "0 6 * * *", "vigilancia": "*/5 * * * *", "parte": "30 10 * * 1", "radar": "30 7 * * 1", "metricas-semanales": "0 8 * * 1",
           "revision-mensual": "30 8 1 * *", "autoridad": "0 10 2 * *"}
SOLO_SI_SE_ACTIVA = {"visibilidad-ia": "0 9 1 * *"}   # mensual (cada quince días es ruido); coste externo: la activa la persona


def _valido(horario) -> bool:
    return isinstance(horario, str) and len(horario.split()) == 5 and all(
        all(ch in "0123456789*/,-" for ch in campo) for campo in horario.split())


def plan(slug: str) -> list:
    cfg = C.leer(slug)
    propios = cfg.get("crons") or {}
    out = []
    for nombre in list(DEFECTO) + [n for n in propios if n not in DEFECTO]:
        horario = propios.get(nombre, DEFECTO.get(nombre))
        if horario is None and nombre in SOLO_SI_SE_ACTIVA:
            continue
        if not horario:
            continue
        if not _valido(horario):
            raise B.Rechazo(f"Horario no válido para {nombre}: «{horario}» (formato cron de 5 campos)")
        if not _cargar("hseo_aterrizaje").permitido(slug, nombre):   # web nueva: su paso del aterrizaje aún no está
            continue
        if nombre == "datos":
            out.append({"nombre": "datos", "horario": horario, "orden": ["datos", "recoger", slug]})
            continue
        if nombre in ("parte", "vigilancia"):
            out.append({"nombre": nombre, "horario": horario, "orden": [nombre, slug]})
            continue
        try:
            PL.plan(nombre, slug)   # ¿se puede lanzar con lo que tiene configurado?
        except B.Rechazo:
            continue
        out.append({"nombre": nombre, "horario": horario, "orden": ["lanzar", slug, nombre]})
    for nombre, horario in SOLO_SI_SE_ACTIVA.items():
        if propios.get(nombre) and nombre not in [x["nombre"] for x in out]:
            try:
                PL.plan(nombre, slug)
            except B.Rechazo:
                continue
            if not _valido(propios[nombre]):
                raise B.Rechazo(f"Horario no válido para {nombre}: «{propios[nombre]}»")
            out.append({"nombre": nombre, "horario": propios[nombre], "orden": ["lanzar", slug, nombre]})
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 2 or a[0] != "plan":
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    try:
        print(json.dumps(plan(a[1]), ensure_ascii=False))
    except B.Rechazo as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
