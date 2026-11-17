"""hermes-seo — canal DASHBOARD: la pestaña «SEO» del panel web de Hermes (/api/plugins/hermes-seo/).

Enseña la cartera, las puertas, las métricas, los cambios y la configuración de cada web. NO decide puertas (se deciden
en Telegram o por correo). De la configuración solo deja cambiar lo seguro (negocio, reglas, guías, competidores, ritmo,
objetivos, motores de IA); cómo se publica, el contacto y las claves, nunca (con la coordinadora). Cada cambio queda en
config.jsonl de la web con «panel:<persona>». La identidad sale de la sesión del panel (con login: el email o el id de la cuenta; en modo local, 127.0.0.1 y sin
login: el usuario del sistema). Debe figurar en aprobadores.json con canal "dashboard". Copiado y adaptado de
hermes-sdd (dashboard/plugin_api.py).
"""
from __future__ import annotations

import getpass
import importlib.util
import json
import re
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
                        "encargos": [{"id": e["id"], "nombre": e["nombre"], "estado": e.get("estado")} for e in abiertos],
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


# ── Configuración de cada web: se ve entera; solo se cambia lo seguro (sin claves, sin cómo se publica) ──
# (clave, etiqueta, tipo, ayuda). tipo: texto | lista | numero | fecha | si-no
EDITABLES = [
    ("negocio.publico", "Público", "texto", "A quién se escribe."),
    ("negocio.voz", "Voz", "texto", "Cómo suena la web."),
    ("negocio.objetivo", "Objetivo", "texto", "Qué se quiere conseguir, con cifra y fecha."),
    ("negocio.conversion", "Qué cuenta como conversión", "texto", ""),
    ("negocio.producto", "Datos del producto confirmados", "texto", "Mandan sobre lo que diga la web (precios, límites…)."),
    ("capacidades.publicacion.reglas", "Reglas de formato", "texto", "Cómo tiene que venir escrito el texto."),
    ("capacidades.publicacion.guias", "Guías que se leen antes de escribir", "lista", "Un fichero o URL por línea."),
    ("competidores", "Competidores", "lista", "Un dominio por línea."),
    ("ia.motores", "Motores de la visibilidad en IA", "lista", "claude, chatgpt o brave; ChatGPT y Brave cuestan dinero."),
    ("politicas.tope_semanal", "Piezas nuevas por semana (tope)", "numero", ""),
    ("politicas.congelado_hasta", "Sin piezas nuevas hasta", "fecha", "AAAA-MM-DD; vacío = sin congelar."),
    ("politicas.pausado", "En pausa", "si-no", "En pausa no se lanza trabajo nuevo."),
    ("criterio.fecha", "Fecha del objetivo", "fecha", ""),
    ("criterio.objetivo_clics", "Objetivo de clics al mes", "numero", ""),
    ("criterio.objetivo_descargas", "Objetivo de descargas al mes", "numero", ""),
    ("criterio.objetivo_ventas", "Objetivo de ventas al mes", "numero", ""),
]
EDITABLE = {c: t for c, _, t, _ in EDITABLES}


def _valor(cfg: dict, clave: str):
    v = cfg
    for p in clave.split("."):
        v = v.get(p) if isinstance(v, dict) else None
    return v


def _como_trabaja(slug: str) -> list:
    PL, M = _cargar("hseo_pipelines"), _cargar("hseo_modelos")
    out = []
    for pid, p in sorted(PL.listar(slug).items()):
        etapas = []
        for s in p.get("etapas", []):
            ej = s.get("ejecutor", "hermes")
            try:
                mod = M.para(s["id"], ej, slug, s.get("perfil"))
            except Exception:   # noqa: BLE001
                mod = ""
            etapas.append({"id": s["id"], "skill": s.get("skill"), "ejecutor": "Claude Code" if ej == "claude" else "Hermes",
                           "modelo": mod or "el del perfil"})
        out.append({"id": pid, "nombre": p.get("nombre", pid), "propia": "/clientes/" in str(p.get("_origen", "")),
                    "hereda": p.get("_hereda"), "etapas": etapas, "puerta": (p.get("puerta") or {}).get("tipo")})
    return out


@router.get("/config/{slug}")
async def ver_config(slug: str, request: Request):
    _actor(request)
    def hacer():
        cfg = _accion(lambda: C.leer(slug))
        pub = cfg["capacidades"].get("publicacion") or {}
        cont = cfg.get("contacto") or {}
        try:
            tareas = [{"nombre": t["nombre"], "horario": t["horario"]} for t in _cargar("hseo_crons").plan(slug)]
        except Exception as e:   # noqa: BLE001
            tareas = [{"nombre": "error", "horario": str(e)}]
        try:
            at = _cargar("hseo_aterrizaje").estado(slug)
            alta = None if not at else {"hechos": len([1 for v in at["pasos"].values() if v.get("ok") or v.get("omitido")]),
                                        "completo": bool(at.get("completo"))}
        except Exception:   # noqa: BLE001
            alta = None
        hist = []
        try:
            for l in (C.carpeta(slug) / "config.jsonl").read_text().splitlines()[-15:]:
                r = json.loads(l)
                hist.append({"ts": r.get("ts"), "quien": r.get("quien"), "clave": r.get("clave"),
                             "antes": json.dumps(r.get("antes"), ensure_ascii=False)[:160],
                             "despues": json.dumps(r.get("despues"), ensure_ascii=False)[:160]})
        except OSError:
            pass
        prep = pub.get("preparar") or {}
        return {
            "slug": slug, "nombre": cfg["nombre"], "url": cfg["url"],
            "web": {"Idioma principal": cfg.get("idioma"), "Idiomas": ", ".join(cfg.get("idiomas") or [cfg.get("idioma")]),
                    "Mercados": ", ".join(m.get("pais", "") for m in cfg.get("mercados") or []),
                    "Zona horaria": cfg.get("zona_horaria"), "Estado de la web": cfg.get("estado_web"),
                    "Idioma de los informes": cfg.get("idioma_informes") or "es"},
            "publicacion": {"Cómo publica": pub.get("adaptador"),
                            "Dónde": pub.get("url") or pub.get("repo") or pub.get("url_api") or "—",
                            "Cómo lo lleva a su sitio (preparar)": (f"{prep['skill']} con {'Claude Code' if prep.get('ejecutor') == 'claude' else 'Hermes'}"
                                                                    if prep else "el del plugin (Hermes)"),
                            "Analítica": (cfg["capacidades"].get("analitica") or {}).get("adaptador")},
            "contacto": {"Correo": cont.get("correo") or "—", "Canal": cont.get("canal") or "telegram",
                         "Confirmado": "sí" if cont.get("verificado") else "no"},
            "capacidades": sorted(C.capacidades(cfg)),
            "editables": [{"clave": c, "etiqueta": e, "tipo": t, "ayuda": a, "valor": _valor(cfg, c)} for c, e, t, a in EDITABLES],
            "como_trabaja": _como_trabaja(slug), "tareas": tareas, "alta": alta, "historial": list(reversed(hist)),
        }
    return await run_in_threadpool(hacer)


@router.post("/config/{slug}")
async def cambiar_config(slug: str, request: Request):
    persona, _, _ = _actor(request)
    cuerpo = await request.json()
    clave, valor = cuerpo.get("clave"), cuerpo.get("valor")
    tipo = EDITABLE.get(clave)
    if not tipo:
        raise HTTPException(403, "Eso no se cambia desde el panel (cómo se publica, el contacto y las claves, con la coordinadora).")
    if tipo == "texto":
        if not isinstance(valor, str) or len(valor) > 4000:
            raise HTTPException(422, "Texto de hasta 4.000 caracteres.")
        valor = valor.strip()
    elif tipo == "lista":
        if isinstance(valor, str):
            valor = [x.strip() for x in valor.splitlines() if x.strip()]
        if not isinstance(valor, list) or len(valor) > 30 or not all(isinstance(x, str) and len(x) <= 300 for x in valor):
            raise HTTPException(422, "Una lista de hasta 30 líneas.")
    elif tipo == "numero":
        try:
            valor = int(valor)
        except (TypeError, ValueError):
            raise HTTPException(422, "Un número entero.")
    elif tipo == "fecha":
        valor = (valor or "").strip() or None
        if valor is not None and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor):
            raise HTTPException(422, "Fecha AAAA-MM-DD o vacío.")
    elif tipo == "si-no":
        valor = bool(valor)
    def hacer():
        _accion(lambda: C.config(slug, clave, valor, f"panel:{persona}"))
        if (C.carpeta(slug) / "aterrizaje.json").exists():
            try:
                _cargar("hseo_aterrizaje").comprobar(slug)
            except Exception:   # noqa: BLE001
                pass
        return {"ok": True}
    return await run_in_threadpool(hacer)
