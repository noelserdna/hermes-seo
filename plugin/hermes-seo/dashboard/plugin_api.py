"""hermes-seo — canal DASHBOARD: la pestaña «SEO» del panel web de Hermes (/api/plugins/hermes-seo/).

Como Telegram, este canal no firma: registra la decisión y el gateway la firma al acabar la ventana para deshacer.
La identidad sale de la sesión del panel (con login: el email o el id de la cuenta; en modo local, 127.0.0.1 y sin
login: el usuario del sistema). Debe figurar en aprobadores.json con canal "dashboard". Copiado y adaptado de
hermes-sdd (dashboard/plugin_api.py).
"""
from __future__ import annotations

import getpass
import importlib.util
import json
import socket
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from starlette.concurrency import run_in_threadpool

AQUI = Path(__file__).resolve().parent.parent


def _cargar(nombre: str):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, AQUI / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


B, C, PU, E = _cargar("hseo_base"), _cargar("hseo_clientes"), _cargar("hseo_puertas"), _cargar("hseo_encargos")
router = APIRouter()
CAMPOS = ("id", "tipo", "cliente", "encargo", "titulo", "texto", "opciones", "estado", "creada", "firmar_en", "error",
          "firma", "resultado")


def _actor(request: Request) -> tuple:
    sesion = getattr(request.state, "session", None)
    if sesion is not None:
        ident, prueba = (sesion.email or sesion.user_id), {"proveedor": sesion.provider, "cuenta": sesion.user_id}
    elif getattr(request.state, "native_http_principal", None) and getattr(request.app.state, "auth_required", None) is False:
        ident, prueba = getpass.getuser(), {"modo": "desktop", "host": socket.gethostname().split(".")[0]}
    else:
        local = getattr(request.app.state, "auth_required", None) is False
        cliente = request.client.host if request.client else ""
        if not local or cliente not in ("127.0.0.1", "::1", "localhost"):
            raise HTTPException(403, "sin sesión del panel no hay persona autorizada")
        ident, prueba = getpass.getuser(), {"modo": "local", "host": socket.gethostname().split(".")[0]}
    persona, _ = PU.persona_de("dashboard", ident)
    if not persona:
        raise HTTPException(403, f"{ident} no figura en aprobadores.json con canal dashboard")
    return persona, ident, prueba


def _accion(f):
    try:
        return f()
    except B.Rechazo as e:
        raise HTTPException(409, str(e))


def _vista(p: dict) -> dict:
    v = {k: p.get(k) for k in CAMPOS}
    v["jev"] = PU.describir_jev(p)
    v["decision"] = {k: (p.get("decision") or {}).get(k) for k in ("verbo", "texto", "at")}
    v["decidio"] = ((p.get("decision") or {}).get("actor") or {}).get("persona")
    return v


@router.get("/webs")
async def webs(request: Request):
    _actor(request)
    def hacer():
        out = []
        for s in C.listar():
            cfg = C.leer(s)
            abiertos = E.listar(s, abiertos=True)
            pend = [p for p in PU.puertas(("abierta", "decidida", "error")) if p["cliente"] == s]
            out.append({"slug": s, "nombre": cfg["nombre"], "url": cfg["url"], "estado_web": cfg["estado_web"],
                        "publica": cfg["capacidades"]["publicacion"].get("adaptador"),
                        "capacidades": sorted(C.capacidades(cfg)), "pausada": bool((cfg.get("politicas") or {}).get("pausado")),
                        "jev": PU.modo_jev(s), "encargos": [{"id": e["id"], "nombre": e["nombre"], "estado": e.get("estado")} for e in abiertos],
                        "puertas": len(pend)})
        return out
    return await run_in_threadpool(hacer)


@router.get("/sistema")
async def sistema(request: Request):
    _actor(request)
    return await run_in_threadpool(lambda: {"disco": B.disco()})


@router.get("/puertas")
async def puertas(request: Request):
    _actor(request)
    return [_vista(p) for p in PU.puertas(("abierta", "decidida", "error"))]


@router.post("/decidir/{gid}")
async def decidir(gid: str, request: Request):
    persona, ident, prueba = _actor(request)
    body = await request.json()
    prueba = {**prueba, "ua": (request.headers.get("user-agent") or "")[:60]}
    return _vista(_accion(lambda: PU.decidir(gid, str(body.get("verbo", "")), str(body.get("texto", "")), persona,
                                            "dashboard", ident, prueba)))


@router.post("/deshacer/{gid}")
async def deshacer(gid: str, request: Request):
    persona, _, _ = _actor(request)
    return _vista(_accion(lambda: PU.deshacer(gid, persona)))


@router.get("/metricas/{slug}")
async def metricas(slug: str, request: Request, dias: int = 28):
    _actor(request)
    return await run_in_threadpool(lambda: _accion(lambda: _cargar("hseo_datos").resumen(slug, max(7, min(dias, 180)))))


@router.get("/cambios/{slug}")
async def cambios(slug: str, request: Request):
    _actor(request)
    def hacer():
        out = []
        try:
            for l in (C.carpeta(slug) / "cambios.jsonl").read_text().splitlines()[-30:]:
                r = json.loads(l)
                out.append({k: r.get(k) for k in ("id", "ts", "clase", "hipotesis", "url", "adaptador", "resultado", "firma")})
        except (OSError, B.Rechazo):
            pass
        return list(reversed(out))
    return await run_in_threadpool(hacer)
