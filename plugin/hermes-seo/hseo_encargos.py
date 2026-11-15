"""Encargos: una pipeline lanzada para un cliente. Orquesta sin interpretar (como lanzar.sh de hermes-sdd).

  clientes/<slug>/encargos/<id>/
    encargo.json   pipeline, parámetros, etapas que corren, tarjetas, estado
    brief.md       lo que se pidió (parámetros y, si lo hay, el brief de quien lo pidió)
    <salida>       lo que deja cada etapa (investigacion.md, borrador.md, verificacion.md…)
    .estado/       candado y salidas de cada ejecución (runs/)
  clientes/<slug>/encargos.jsonl   una línea por encargo lanzado (las políticas cuentan las piezas nuevas aquí)

Cada etapa es una tarjeta del tablero del cliente (tablero = slug), asignada a la estación (seo-estacion), con el cuerpo
«Ejecuta: bash <arnés>/etapa.sh <slug> <encargo> <etapa>» y encadenada con --parent a la anterior.

CLI:
  hseo_encargos.py lanzar <slug> <pipeline> [--param k=v]… [--brief FICHERO] [--excepcion] [--quien Q] [--seco]
  hseo_encargos.py ver <slug> <encargo>
  hseo_encargos.py listar <slug> [--abiertos]
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import secrets
import shutil
import subprocess
import sys
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
PL = _cargar("hseo_pipelines")
Rechazo = B.Rechazo
ESTACION = "seo-estacion"


def _hermes() -> str:
    return os.environ.get("HERMES_BIN") or shutil.which("hermes") or str(Path.home() / ".local" / "bin" / "hermes")


def kanban(slug: str, *args: str) -> str:
    """hermes kanban --board <slug> …; Rechazo con el error si falla."""
    r = subprocess.run([_hermes(), "kanban", "--board", slug, *args], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Rechazo(f"El kanban de Hermes falló: {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout


def asegurar_tablero(slug: str) -> None:
    r = subprocess.run([_hermes(), "kanban", "boards", "list", "--json"], capture_output=True, text=True, timeout=60)
    try:
        if any(b.get("slug") == slug for b in json.loads(r.stdout or "[]")):
            return
    except ValueError:
        pass
    cfg = C.leer(slug)
    r = subprocess.run([_hermes(), "kanban", "boards", "create", slug, "--name", cfg.get("nombre") or slug,
                        "--description", f"SEO de {cfg['dominio']} (hermes-seo)",
                        "--default-workdir", str(C.carpeta(slug))], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise Rechazo(f"No pude crear el tablero de {slug}: {(r.stderr or r.stdout).strip()[-300:]}")


def raiz_arnes() -> Path:
    return PL.raiz()


def _id(pid: str, params: dict) -> str:
    base = next((v for v in params.values() if v), "") or datetime.now(timezone.utc).strftime("%Y%m%d")
    base = re.sub(r"https?://", "", str(base).lower())
    base = re.sub(r"[^a-z0-9]+", "-", base).strip("-")[:32].strip("-") or "x"
    return f"{pid}-{base}-{secrets.token_hex(2)}"


def _titulo(s: dict, params: dict) -> str:
    t = s.get("titulo") or s["id"]
    for k, v in params.items():
        t = t.replace("{" + k + "}", str(v)[:60])
    return t


def carpeta(slug: str, eid: str) -> Path:
    if not re.fullmatch(r"[a-z0-9-]{3,80}", eid or ""):
        raise Rechazo("id de encargo no válido")
    return C.carpeta(slug) / "encargos" / eid


def leer(slug: str, eid: str) -> dict:
    e = B.leer(carpeta(slug, eid) / "encargo.json")
    if not e:
        raise Rechazo(f"No conozco el encargo {eid} de {slug}")
    return e


def guardar(slug: str, e: dict) -> None:
    B.escribir(carpeta(slug, e["id"]) / "encargo.json", e)


MAX_DECISIONES = 3   # puertas que esperan a una persona por web (las abiertas más los encargos que acabarán en una)


def decide(p: dict | None) -> bool:
    """¿Aprobar la puerta de esta pipeline (o de este encargo) ejecuta algo? Si no, es un informe."""
    puerta = (p or {}).get("puerta")
    return bool(puerta) and str(puerta.get("al_aprobar", "nada")) != "nada"


def duplicado(slug: str, pid: str, params: dict) -> dict | None:
    for e in listar(slug, abiertos=True):
        if e.get("pipeline") != pid or (e.get("params") or {}) != params:
            continue
        if e.get("estado") in ("en-curso", "parado", "en-vuelta") or (e.get("estado") == "en-puerta" and decide(e)):
            return e
    return None


def decisiones_pendientes(slug: str, excluir: str = "") -> int:
    return sum(1 for e in listar(slug, abiertos=True)
               if decide(e) and e.get("id") != excluir and e.get("estado") in ("en-curso", "parado", "en-puerta", "en-vuelta"))


def lanzar(slug: str, pid: str, params: dict | None = None, brief: str = "", excepcion: bool = False,
           quien: str = "", seco: bool = False, origen: str | None = None, en_lugar_de: str = "") -> dict:
    """Valida (parámetros, capacidades, políticas), crea la carpeta del encargo y sus tarjetas encadenadas."""
    params = {k: str(v).strip() for k, v in (params or {}).items() if str(v).strip()}
    r = PL.plan(pid, slug)
    p = r["pipeline"]
    if origen:   # continuación de un encargo: hereda sus parámetros (los que admite esta pipeline) y sus salidas
        previo = leer(slug, origen)
        params = {**{k: v for k, v in (previo.get("params") or {}).items() if k in (p.get("parametros") or {})}, **params}
    falta = [k for k in (p.get("parametros") or {}) if k not in params]
    if falta:
        raise Rechazo(f"«{p['nombre']}» necesita: " + "; ".join(f"{k} ({p['parametros'][k]})" for k in falta))
    sobra = [k for k in params if k not in (p.get("parametros") or {})]
    if sobra:
        raise Rechazo(f"«{p['nombre']}» no admite: {', '.join(sobra)}")
    # una continuación ya pasó las políticas al empezar (la pausa sí cuenta siempre)
    PL.politicas(pid, slug, excepcion=excepcion or bool(origen))
    if not origen and params.get("url") and not excepcion:   # una página de una tanda abierta no se toca por otro lado
        try:
            T = _cargar("hseo_tandas")
            for t in T.abiertas(slug):
                if T._norm(params["url"]) in {T._norm(u) for u in t.get("control", [])} | {T._norm(p["url"]) for p in t.get("paginas", [])}:
                    raise Rechazo(f"{params['url']} está en la tanda {t['id']} (se mide hasta su veredicto): no se toca por otro lado")
        except Rechazo:
            raise
        except Exception:   # noqa: BLE001
            pass
    if not origen:
        igual = duplicado(slug, pid, params)
        if igual:   # el mismo trabajo ya está en marcha: no se lanza otro (ni otra puerta igual)
            return {**igual, "duplicado": True}
        if decide(p) and not excepcion and not seco:
            n = decisiones_pendientes(slug, excluir=en_lugar_de)   # la puerta que se está firmando deja su hueco
            if n >= MAX_DECISIONES:
                raise Rechazo(f"{C.leer(slug).get('nombre') or slug} ya tiene {n} decisiones pendientes: "
                              f"decide alguna antes de lanzar «{p['nombre']}».")
    eid = _id(pid, params)
    etapas = [{"id": s["id"], "titulo": _titulo(s, params), "max_runtime": s.get("max_runtime", "60m")} for s in r["etapas"]]
    plan = {"id": eid, "cliente": slug, "pipeline": pid, "nombre": p["nombre"], "params": params,
            "etapas": etapas, "saltadas": [{"id": s["id"], "falta": s["falta"]} for s in r["saltadas"]],
            "puerta": p.get("puerta"), "nueva_pieza": bool(p.get("nueva_pieza")), "excepcion": excepcion,
            "quien": quien, "creado": B.ahora(), "estado": "en-curso", "tarjetas": {}, "origen": origen,
            "heredados": []}
    if seco:
        return plan
    d = carpeta(slug, eid)
    d.mkdir(parents=True, exist_ok=False)
    (d / ".estado" / "runs").mkdir(parents=True, exist_ok=True)
    lineas = [f"# {p['nombre']}", "", f"- Cliente: {slug}", f"- Pedido por: {quien or '—'} ({plan['creado']})"]
    lineas += [f"- {k}: {v}" for k, v in params.items()]
    if excepcion:
        lineas.append("- Excepción a las políticas pedida expresamente por una persona")
    if origen:
        lineas.append(f"- Continúa el encargo {origen}: sus resultados están en esta carpeta")
        po = carpeta(slug, origen)
        for f in sorted(po.iterdir()):
            if f.is_file() and not f.name.startswith(".") and f.name not in ("encargo.json", "brief.md", "contexto-cliente.md"):
                shutil.copy2(f, d / f.name)
                plan["heredados"].append(f.name)
        if (po / "brief.md").exists():
            shutil.copy2(po / "brief.md", d / "brief-origen.md")
            plan["heredados"].append("brief-origen.md")
    (d / "brief.md").write_text("\n".join(lineas) + ("\n\n## Brief\n\n" + brief.strip() if brief.strip() else "") + "\n")
    guardar(slug, plan)
    _tarjetas(slug, plan, 0, "")
    guardar(slug, plan)
    B.anotar(C.carpeta(slug) / "encargos.jsonl", {"ts": plan["creado"], "id": eid, "pipeline": pid, "quien": quien,
                                                 "nueva_pieza": plan["nueva_pieza"] and not origen, "excepcion": excepcion,
                                                 "origen": origen})
    return plan


def _tarjetas(slug: str, enc: dict, desde: int, sufijo: str) -> None:
    """Crea las tarjetas de enc["etapas"][desde:], encadenadas; guarda sus ids en enc["tarjetas"]."""
    asegurar_tablero(slug)
    d, arnes, padre = carpeta(slug, enc["id"]), raiz_arnes(), None
    for s in enc["etapas"][desde:]:
        args = ["create", s["titulo"], "--assignee", ESTACION, "--workspace", f"dir:{d}",
                "--max-runtime", s["max_runtime"], "--max-retries", "1",
                "--idempotency-key", f"{enc['id']}-{s['id']}{sufijo}",
                "--body", f"Ejecuta: bash {arnes}/etapa.sh {slug} {enc['id']} {s['id']}", "--json"]
        if padre:
            args += ["--parent", padre]
        out = kanban(slug, *args)
        try:
            tid = json.loads(out)["id"]
        except (ValueError, KeyError):
            raise Rechazo(f"El kanban no devolvió el id de la tarjeta: {out[-200:]}")
        enc["tarjetas"][s["id"]] = tid
        padre = tid


def rehacer_desde(slug: str, eid: str, etapa: str, texto: str, quien: str = "", accion: str = "rehacer",
                  de: str = "persona") -> dict:
    """«Cambios» en una puerta (o un reintento, o la vuelta de la verificación): la etapa indicada y las siguientes se
    vuelven a hacer; con `texto`, lo que se pidió. `de` = persona | verificacion (ficheros de feedback distintos, para
    que la vuelta automática no pise lo que pidió una persona)."""
    enc = leer(slug, eid)
    ids = [s["id"] for s in enc["etapas"]]
    if etapa not in ids:
        raise Rechazo(f"La etapa {etapa} no es de este encargo")
    d = carpeta(slug, eid)
    (d / ".estado").mkdir(parents=True, exist_ok=True)
    if texto.strip():
        nombre = f"feedback-{etapa}.txt" if de == "persona" else f"feedback-{de}-{etapa}.txt"
        (d / ".estado" / nombre).write_text(texto.strip() + "\n")
    enc["rondas"] = int(enc.get("rondas") or 0) + 1
    enc["estado"] = "en-curso"
    enc.pop("puerta_id", None)
    for s in enc["etapas"][ids.index(etapa):]:   # las tarjetas viejas de esas etapas no deben quedarse esperando
        viejo = (enc.get("tarjetas") or {}).get(s["id"])
        if viejo:
            try:
                kanban(slug, "archive", viejo)
            except Rechazo:
                pass   # ya hecha o ya archivada
    _tarjetas(slug, enc, ids.index(etapa), f"-r{enc['rondas']}")
    guardar(slug, enc)
    B.anotar(d / ".estado" / "historial.jsonl", {"ts": B.ahora(), "accion": accion, "desde": etapa,
                                                "texto": texto, "quien": quien, "ronda": enc["rondas"]})
    return enc


def vueltas_pendientes() -> list:
    """Encargos que la verificación devolvió (estado en-vuelta): vuelven a la etapa indicada con los cambios pedidos.
    Lo llama el bucle del plugin (y «hseo vueltas»). Devuelve [(web, encargo, desde)]."""
    hechas = []
    for slug in C.listar():
        for e in listar(slug, abiertos=True):
            v = e.get("vuelta_pendiente")
            if e.get("estado") != "en-vuelta" or not v:
                continue
            try:
                enc = rehacer_desde(slug, e["id"], v["desde"], v.get("texto", ""), quien="verificación",
                                    accion="vuelta-verificacion", de="verificacion")
                enc.pop("vuelta_pendiente", None)
                guardar(slug, enc)
                hechas.append((slug, e["id"], v["desde"]))
            except Rechazo as x:
                e["estado"] = "parado"
                e["vuelta_error"] = str(x)[:300]
                guardar(slug, e)
    return hechas


def listar(slug: str, abiertos: bool = False) -> list:
    d = C.carpeta(slug) / "encargos"
    out = []
    for f in sorted(d.glob("*/encargo.json")) if d.is_dir() else []:
        e = B.leer(f) or {}
        if e and (not abiertos or e.get("estado") not in ("cerrado", "descartado", "hecho")):
            out.append(e)
    return sorted(out, key=lambda e: e.get("creado", ""))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hseo_encargos.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("lanzar"); l.add_argument("slug"); l.add_argument("pipeline")
    l.add_argument("--param", action="append", default=[]); l.add_argument("--brief")
    l.add_argument("--excepcion", action="store_true"); l.add_argument("--quien", default="")
    l.add_argument("--seco", action="store_true")
    v = sub.add_parser("ver"); v.add_argument("slug"); v.add_argument("encargo")
    ls = sub.add_parser("listar"); ls.add_argument("slug"); ls.add_argument("--abiertos", action="store_true")
    x = ap.parse_args(argv)
    try:
        if x.cmd == "lanzar":
            params = {}
            for kv in x.param:
                if "=" not in kv:
                    raise Rechazo(f"Parámetro sin «=»: {kv}")
                k, v = kv.split("=", 1)
                params[k.strip()] = v
            brief = Path(x.brief).read_text() if x.brief else ""
            e = lanzar(x.slug, x.pipeline, params, brief, x.excepcion, x.quien, x.seco)
            print(json.dumps({"encargo": e["id"], "etapas": [s["id"] for s in e["etapas"]],
                              "saltadas": e["saltadas"], "tarjetas": e["tarjetas"], "seco": x.seco,
                              "duplicado": bool(e.get("duplicado"))}, ensure_ascii=False))
        elif x.cmd == "ver":
            print(json.dumps(leer(x.slug, x.encargo), ensure_ascii=False, indent=2))
        elif x.cmd == "listar":
            for e in listar(x.slug, x.abiertos):
                print(f"{e['id']:44} {e.get('estado', ''):12} {e.get('nombre', '')}")
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
