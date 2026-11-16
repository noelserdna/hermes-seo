"""Doble de un servidor MCP con registro de agentes de auth.md (para tests/mcp.sh). Estado en $MCP_DOBLE_ESTADO
(JSON): cuántos sondeos quedan pendientes, tokens emitidos, llamadas recibidas, si el acceso está revocado."""
import json
import os
import urllib.parse

ORIGEN = "https://web.test"


def _e():
    f = os.environ["MCP_DOBLE_ESTADO"]
    try:
        return json.load(open(f))
    except (OSError, ValueError):
        return {"pendientes": 1, "tokens": 0, "llamadas": [], "revocado": False, "id": 100}


def _g(e):
    json.dump(e, open(os.environ["MCP_DOBLE_ESTADO"], "w"))


def _r(codigo, datos, cab=None):
    return codigo, {"content-type": "application/json", **(cab or {})}, json.dumps(datos)


HERRAMIENTAS = [
    {"name": "articulos", "annotations": {"readOnlyHint": True}},
    {"name": "estadisticas_blog", "annotations": {"readOnlyHint": True}},
    {"name": "embudo", "annotations": {"readOnlyHint": True}},
    {"name": "guardar_articulo", "annotations": {"readOnlyHint": False}},
    {"name": "despublicar_articulo", "annotations": {"readOnlyHint": False, "destructiveHint": True}},
]


def pedir(metodo, url, datos, cab, form):
    e = _e()
    ruta = urllib.parse.urlsplit(url).path
    if ruta == "/.well-known/oauth-authorization-server":
        return _r(200, {"issuer": ORIGEN, "token_endpoint": f"{ORIGEN}/oauth/token",
                        "agent_auth": {"identity_endpoint": f"{ORIGEN}/agent/identity", "identity_types_supported": ["service_auth"]}})
    if ruta == "/agent/identity":
        if datos.get("type") != "service_auth" or "@" not in datos.get("login_hint", ""):
            return _r(400, {"error": "invalid_request"})
        e["agente"] = datos.get("agent_name"); _g(e)
        return _r(200, {"claim_token": "claim-secreto", "claim": {"user_code": "123456", "verification_uri": f"{ORIGEN}/agente/reclamar",
                                                                  "expires_in": 600, "interval": 0}})
    if ruta == "/oauth/token":
        if datos.get("grant_type") == "urn:workos:agent-auth:grant-type:claim":
            if e["pendientes"] > 0:
                e["pendientes"] -= 1; _g(e)
                return _r(400, {"error": "authorization_pending"})
            e["tokens"] += 1; _g(e)
            return _r(200, {"access_token": f"tok{e['tokens']}", "expires_in": 3600, "scope": "lectura cambios",
                            "identity_assertion": "asercion-secreta"})
        if datos.get("grant_type") == "urn:ietf:params:oauth:grant-type:jwt-bearer":
            if e["revocado"] or datos.get("assertion") != "asercion-secreta":
                return _r(400, {"error": "invalid_grant"})
            e["tokens"] += 1; _g(e)
            return _r(200, {"access_token": f"tok{e['tokens']}", "expires_in": 3600, "scope": "lectura cambios"})
        return _r(400, {"error": "unsupported_grant_type"})
    if ruta == "/mcp":
        if not str(cab.get("Authorization", "")).startswith("Bearer tok") or e["revocado"]:
            return 401, {}, ""
        m = datos.get("method")
        if m == "initialize":
            return _r(200, {"jsonrpc": "2.0", "id": datos["id"], "result": {"protocolVersion": "2025-06-18"}}, {"mcp-session-id": "s1"})
        if m == "notifications/initialized":
            return 202, {}, ""
        if m == "tools/list":
            return _r(200, {"jsonrpc": "2.0", "id": datos["id"], "result": {"tools": HERRAMIENTAS}})
        if m == "tools/call":
            p = datos["params"]
            e["llamadas"].append(p); _g(e)
            if p["name"] == "guardar_articulo":
                a = p["arguments"]
                if not a.get("titulo"):
                    return _r(200, {"jsonrpc": "2.0", "id": datos["id"], "result": {"isError": True, "content": [{"type": "text", "text": "Falta el título"}]}})
                e["id"] += 1; _g(e)
                sl = a.get("slug"); pre = "" if a.get("idioma") == "en" else "/es"
                res = {"ok": True, "id": e["id"], "lang": a.get("idioma"), "slug": sl, "url": f"{ORIGEN}{pre}/{sl}",
                       "warnings": ["meta corta"] if a.get("idioma") == "en" else []}
            elif p["name"] == "embudo":
                res = {"months": [{"month": "2026-10", "visits": 10, "downloads": 1, "checkouts": 0, "sales": 0},
                                  {"month": "2026-11", "visits": 425, "downloads": 3, "checkouts": 2, "sales": 1}]}
            else:
                res = {"posts": {"published": 8}, "months": [{"month": "2026-11", "visits": 87, "buscadores": 5, "ia": 1}]}
            # como el servidor real: el resultado va como texto JSON, en un flujo SSE
            cuerpo = json.dumps({"jsonrpc": "2.0", "id": datos["id"], "result": {"content": [{"type": "text", "text": json.dumps(res)}]}})
            return 200, {"content-type": "text/event-stream"}, f"event: message\ndata: {cuerpo}\n\n"
    return 404, {}, "no"
