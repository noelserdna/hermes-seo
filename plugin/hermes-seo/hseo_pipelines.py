"""Pipelines como datos: qué etapas tiene cada trabajo, quién hace cada una y en qué puerta acaba.

Una pipeline es un JSON en pipelines/<id>.json (del plugin) o en clientes/<slug>/extensiones/pipelines/<id>.json (del
cliente: añade pipelines propias o sustituye una del plugin con el mismo id).

  {"id": "articulo", "nombre": "Artículo nuevo", "descripcion": "…",
   "requiere": ["publicacion"],             capacidades del cliente sin las que no se puede lanzar
   "nueva_pieza": true,                      cuenta para la congelación y el tope semanal del cliente
   "parametros": {"tema": "De qué trata"},   obligatorios al lanzar
   "etapas": [{"id": "investigar", "titulo": "Investigar: {tema}", "perfil": "seo-investigador",
               "skill": "investigacion-a-fondo", "ejecutor": "hermes", "max_runtime": "60m",
               "requiere": [], "salida": "investigacion.md"}, …],
   "puerta": {"tipo": "publicar", "al_aprobar": "publicar"}}     (opcional; se abre al acabar la última etapa)

al_aprobar: nada | publicar | pipeline:<id> (sigue con otra pipeline: mismos parámetros y las salidas de este
encargo) | script:<fichero de extensiones/> [args con {encargo} y {carpeta}] (un script propio de la web).

Una etapa con `requiere` que el cliente no cumple se salta (p. ej. «competencia» sin competidores); una pipeline con
`requiere` que no cumple no se lanza y dice qué falta.

CLI:
  hseo_pipelines.py listar [--cliente SLUG]
  hseo_pipelines.py ver <id> [--cliente SLUG]
  hseo_pipelines.py plan <id> --cliente SLUG       etapas que correrían para ese cliente
  hseo_pipelines.py validar-todas
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
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
Rechazo = B.Rechazo

PERFILES_ROL = ("seo-investigador", "seo-redactor", "seo-verificador", "seo-editor", "seo-analista")
EJECUTORES = ("hermes", "claude", "replay")
TIPOS_PUERTA = ("alta", "plan-tecnico", "plan-editorial", "publicar", "cambio-tecnico", "decision", "veredicto",
                "mantenimiento", "difusion")
AL_APROBAR = re.compile(r"^(nada|publicar|gestiones|pipeline:[a-z0-9-]+|script:[A-Za-z0-9._-]+( [^;&|`$<>]*)?)$")
ID = re.compile(r"^[a-z][a-z0-9-]{1,40}$")
DURACION = re.compile(r"^\d{1,3}[mh]$")


def raiz() -> Path:
    """Carpeta del arnés: el repo (desarrollo) o ~/.hermes/hermes-seo/actual (instalado)."""
    for r in (AQUI.parent.parent, B.home() / "actual"):
        if (r / "pipelines").is_dir():
            return r
    return AQUI.parent.parent


def _dirs(slug: str | None) -> list:
    ds = [raiz() / "pipelines"]
    if slug:
        ds.append(B.home() / "clientes" / B.validar_slug(slug) / "extensiones" / "pipelines")
    return ds


def listar(slug: str | None = None) -> dict:
    """{id: pipeline}; las del cliente sustituyen a las del plugin con el mismo id."""
    out = {}
    for d in _dirs(slug):
        for f in sorted(d.glob("*.json")) if d.is_dir() else []:
            p = B.leer(f)
            if isinstance(p, dict) and p.get("id"):
                out[p["id"]] = {**p, "_origen": str(f)}
    return out


def cargar(pid: str, slug: str | None = None) -> dict:
    p = listar(slug).get(pid)
    if not p:
        raise Rechazo(f"No conozco la pipeline «{pid}». Hay: {', '.join(sorted(listar(slug))) or 'ninguna'}")
    return p


# Datos que el CÓDIGO deja en la carpeta del encargo antes de una etapa («prepara»: [...]): las cifras no las calcula
# el modelo. Cada una escribe datos-<nombre>.json (ver hseo_etapa.preparar).
PREPARA = ("resumen", "citas")

def validar(p: dict) -> list:
    e = []
    if not ID.match(str(p.get("id", ""))):
        e.append("id: minúsculas, números y guiones")
    if not p.get("nombre"):
        e.append("nombre: obligatorio")
    if not isinstance(p.get("requiere", []), list):
        e.append("requiere: una lista")
    if not isinstance(p.get("parametros", {}), dict):
        e.append("parametros: un objeto {nombre: descripción}")
    etapas = p.get("etapas")
    if not isinstance(etapas, list) or not etapas:
        e.append("etapas: al menos una")
        etapas = []
    vistos = set()
    for i, s in enumerate(etapas):
        donde = f"etapas[{i}]"
        if not isinstance(s, dict):
            e.append(f"{donde}: un objeto"); continue
        if not ID.match(str(s.get("id", ""))):
            e.append(f"{donde}.id no válido")
        elif s["id"] in vistos:
            e.append(f"{donde}.id «{s['id']}» repetido")
        prep = s.get("prepara", [])
        if not isinstance(prep, list) or any(x not in PREPARA for x in prep):
            e.append(f"{donde}.prepara: una lista de {', '.join(PREPARA)}")
        if s.get("si_cambios") is not None and s.get("si_cambios") not in vistos:
            e.append(f"{donde}.si_cambios: el id de una etapa ANTERIOR (a la que vuelve si la verificación pide cambios)")
        vistos.add(s.get("id"))
        if s.get("ejecutor", "hermes") not in EJECUTORES:
            e.append(f"{donde}.ejecutor: uno de {', '.join(EJECUTORES)}")
        if s.get("perfil") not in PERFILES_ROL:
            e.append(f"{donde}.perfil: uno de {', '.join(PERFILES_ROL)}")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,60}", str(s.get("skill", ""))):
            e.append(f"{donde}.skill: el nombre de una skill")
        if not DURACION.match(str(s.get("max_runtime", "60m"))):
            e.append(f"{donde}.max_runtime: p. ej. 30m o 2h")
        if not isinstance(s.get("requiere", []), list):
            e.append(f"{donde}.requiere: una lista")
        for marca in re.findall(r"\{(\w+)\}", s.get("titulo", "")):
            if marca not in (p.get("parametros") or {}):
                e.append(f"{donde}.titulo usa {{{marca}}}, que no es un parámetro")
    mem = p.get("memoria")
    if mem is not None and (not isinstance(mem, dict) or not mem.get("pagina") or not mem.get("de")):
        e.append("memoria: {pagina, de, seccion?} (la página fija de la wiki que escribe al acabar)")
    puerta = p.get("puerta")
    if puerta is not None:
        if not isinstance(puerta, dict) or puerta.get("tipo") not in TIPOS_PUERTA:
            e.append(f"puerta.tipo: uno de {', '.join(TIPOS_PUERTA)}")
        elif not AL_APROBAR.match(str(puerta.get("al_aprobar", "nada"))):
            e.append("puerta.al_aprobar: nada | publicar | pipeline:<id> | script:<fichero> [args]")
        elif puerta.get("rehacer") and puerta["rehacer"] not in vistos:
            e.append("puerta.rehacer: el id de una de sus etapas")
    return e


def plan(pid: str, slug: str) -> dict:
    """Las etapas que correrían para este cliente, y las que se saltan y por qué. Rechazo si no se puede lanzar."""
    C = _cargar("hseo_clientes")
    cfg = C.leer(slug)
    p = cargar(pid, slug)
    err = validar(p)
    if err:
        raise Rechazo(f"La pipeline «{pid}» no es válida:\n- " + "\n- ".join(err))
    caps = C.capacidades(cfg)
    falta = [r for r in p.get("requiere", []) if not _cumple(r, caps)]
    if falta:
        raise Rechazo(f"«{p['nombre']}» necesita {', '.join(falta)}, y {cfg['nombre']} no lo tiene configurado")
    corren, saltadas = [], []
    for s in p["etapas"]:
        f = [r for r in s.get("requiere", []) if not _cumple(r, caps)]
        (saltadas if f else corren).append({**s, "falta": f} if f else s)
    if not corren:
        raise Rechazo(f"Para {cfg['nombre']} no quedaría ninguna etapa de «{p['nombre']}»")
    return {"pipeline": p, "etapas": corren, "saltadas": saltadas}


def _cumple(req: str, caps: set) -> bool:
    """«publicacion» lo cumple cualquier adaptador; «publicacion:wordpress» solo ese; «a|b» cualquiera de los dos."""
    return any(r in caps for r in req.split("|"))


def politicas(pid: str, slug: str, excepcion: bool = False, hoy: date | None = None) -> None:
    """Rechazo si las políticas del cliente impiden lanzar ahora esta pipeline. `excepcion`: una persona lo pidió
    expresamente (salta la congelación y el tope, nunca la pausa) y queda anotado."""
    C = _cargar("hseo_clientes")
    cfg = C.leer(slug)
    pol = cfg.get("politicas") or {}
    if pol.get("pausado"):
        raise Rechazo(f"{cfg['nombre']} está en pausa: no se lanza nada hasta reanudarlo")
    p = cargar(pid, slug)
    if not p.get("nueva_pieza") or excepcion:
        return
    hoy = hoy or datetime.now(timezone.utc).date()
    if pol.get("congelado_hasta") and hoy.isoformat() < pol["congelado_hasta"]:
        raise Rechazo(f"{cfg['nombre']} no abre piezas nuevas hasta el {pol['congelado_hasta']} "
                      "(se puede actualizar lo que ya hay; una excepción la pide una persona)")
    tope = int(pol.get("tope_semanal") or 0)
    if tope:
        desde = (hoy - timedelta(days=7)).isoformat()
        n = 0
        try:
            for linea in (C.carpeta(slug) / "encargos.jsonl").read_text().splitlines():
                r = json.loads(linea)
                if r.get("nueva_pieza") and str(r.get("ts", ""))[:10] > desde:
                    n += 1
        except OSError:
            pass
        if n >= tope:
            raise Rechazo(f"{cfg['nombre']} ya tiene {n} pieza(s) nueva(s) esta semana (tope {tope})")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hseo_pipelines.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("listar"); l.add_argument("--cliente")
    v = sub.add_parser("ver"); v.add_argument("id"); v.add_argument("--cliente")
    pl = sub.add_parser("plan"); pl.add_argument("id"); pl.add_argument("--cliente", required=True)
    sub.add_parser("validar-todas")
    x = ap.parse_args(argv)
    try:
        if x.cmd == "listar":
            for pid, p in listar(x.cliente).items():
                print(f"{pid:22} {p.get('nombre', '')}")
        elif x.cmd == "ver":
            print(json.dumps(cargar(x.id, x.cliente), ensure_ascii=False, indent=2))
        elif x.cmd == "plan":
            r = plan(x.id, x.cliente)
            for s in r["etapas"]:
                print(f"▶ {s['id']:18} {s['perfil']:18} {s['skill']}")
            for s in r["saltadas"]:
                print(f"· {s['id']:18} se salta: falta {', '.join(s['falta'])}")
            if r["pipeline"].get("puerta"):
                print(f"🚪 {r['pipeline']['puerta']['tipo']}")
        elif x.cmd == "validar-todas":
            mal = 0
            for pid, p in listar().items():
                err = validar(p)
                if err:
                    mal += 1
                    print(f"{pid}: " + "; ".join(err))
            print("ok" if not mal else f"{mal} con errores")
            return 1 if mal else 0
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
