"""Lo que la coordinadora promete hacer «cuando se apruebe la puerta» (avisar a Bing, pedir la indexación, contárselo a
alguien…). Ella no tiene memoria entre turnos: lo apunta aquí y, cuando la puerta de ese encargo se cierra, el bucle de
puertas (__init__) le da un turno en su tema con el resultado y lo que dejó apuntado.

  hseo seguir <web> <encargo|puerta> "<qué hacer después>"
  hseo seguimientos [<web>]

Se despierta solo con algo apuntado: una puerta sin seguimiento no gasta un turno.
Cuándo está listo: puerta firmada (aprobada, descartada…), con error, o cerrada como informe o caducada. Si se
pidieron cambios, espera a la puerta siguiente del mismo encargo; si se sustituyó, también.
"""
from __future__ import annotations

import importlib.util
import secrets
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
Rechazo = B.Rechazo
MAX_INTENTOS = 10
TODAS = ("abierta", "decidida", "firmada", "error", "informe", "reemplazada", "caducada")


def _f() -> Path:
    return B.home() / "seguimientos.json"


def _todos() -> list:
    d = B.leer(_f(), [])
    return d if isinstance(d, list) else []


def apuntar(cliente: str, objetivo: str, texto: str, quien: str = "") -> dict:
    """objetivo: id de un encargo de la web o de una puerta (g…)."""
    C, PU = _cargar("hseo_clientes"), _cargar("hseo_puertas")
    C.leer(cliente)   # la web existe
    texto = " ".join(str(texto).split())
    if not 3 <= len(texto) <= 1500:
        raise Rechazo("Di qué hay que hacer después (entre 3 y 1500 caracteres)")
    puerta = encargo = None
    if objetivo.startswith("g"):
        p = PU.leer(objetivo)
        if p["cliente"] != cliente:
            raise Rechazo(f"La puerta {objetivo} no es de {cliente}")
        puerta, encargo = objetivo, p.get("encargo")
    else:
        if not _cargar("hseo_encargos").carpeta(cliente, objetivo).exists():
            raise Rechazo(f"{cliente} no tiene el encargo {objetivo}")
        encargo = objetivo
    s = {"id": "s" + secrets.token_hex(4), "cliente": cliente, "encargo": encargo, "puerta": puerta, "texto": texto,
         "quien": quien, "ts": B.ahora(), "intentos": 0}
    B.escribir(_f(), _todos() + [s])
    return s


def pendientes(cliente: str | None = None) -> list:
    return [s for s in _todos() if not cliente or s["cliente"] == cliente]


def _puerta_de(s: dict) -> dict | None:
    PU = _cargar("hseo_puertas")
    if s.get("puerta"):
        try:
            p = PU.leer(s["puerta"])
        except Rechazo:
            return None
        # sustituida o con cambios pedidos: manda la puerta siguiente del mismo encargo
        if s.get("encargo") and (p.get("estado") == "reemplazada" or (p.get("decision") or {}).get("verbo") == "cambios"):
            otras = sorted((q for q in PU.puertas(TODAS) if q.get("encargo") == s["encargo"] and q["cliente"] == s["cliente"]
                            and str(q.get("creada", "")) > str(p.get("creada", ""))), key=lambda q: str(q.get("creada", "")))
            return otras[-1] if otras else None
        return p
    ps = sorted((q for q in PU.puertas(TODAS) if q.get("encargo") == s["encargo"] and q["cliente"] == s["cliente"]),
                key=lambda q: str(q.get("creada", "")))
    return ps[-1] if ps else None


def _cerrada(p: dict | None) -> str:
    """'' si aún no toca; si no, cómo terminó (para el aviso)."""
    if not p:
        return ""
    est, verbo = p.get("estado"), (p.get("decision") or {}).get("verbo")
    if est == "firmada" and verbo != "cambios":
        return f"cerrada ({verbo}): {p.get('resultado') or ''}".strip()
    if est == "error":
        return f"falló al ejecutarse: {p.get('error') or ''}"
    if est in ("informe", "caducada"):
        return {"informe": "cerrada como informe", "caducada": "caducada sin decidir"}[est]
    return ""


def listos() -> list:
    """[(seguimiento, puerta, cómo terminó)] que ya tocan."""
    out = []
    for s in _todos():
        p = _puerta_de(s)
        fin = _cerrada(p)
        if fin:
            out.append((s, p, fin))
    return out


def texto_aviso(s: dict, p: dict, fin: str) -> str:
    return (f"[Aviso automático de hermes-seo, no lo escribe la persona] La puerta «{p.get('titulo', '')}» de "
            f"{s['cliente']} está {fin[:600]}\n\nDejaste apuntado para después: «{s['texto']}»\n\n"
            "Hazlo ahora si sigue teniendo sentido con ese resultado (si la puerta se descartó o falló, no lo hagas: "
            "explícalo). Después cuéntaselo a la persona en corto, con el siguiente paso.")


def quitar(sid: str) -> None:
    B.escribir(_f(), [s for s in _todos() if s["id"] != sid])


def fallo(sid: str) -> int:
    """Suma un intento fallido; devuelve cuántos lleva."""
    todos, n = _todos(), 0
    for s in todos:
        if s["id"] == sid:
            s["intentos"] = n = int(s.get("intentos") or 0) + 1
    B.escribir(_f(), todos)
    return n
