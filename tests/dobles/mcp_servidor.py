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
    {"name": "content_get", "annotations": {"readOnlyHint": True}},
    {"name": "content_update", "annotations": {"readOnlyHint": False}},
    {"name": "despublicar_articulo", "annotations": {"readOnlyHint": False, "destructiveHint": True}},
]


def _oauth(metodo, url, datos, cab, e):
    """Un MCP con OAuth 2.1 normal, como EmDash: RFC 9728 + 8414 bajo /_emdash, registro dinámico y flujo de dispositivo."""
    o, ruta = "https://oauth.test", urllib.parse.urlsplit(url).path
    if ruta == "/.well-known/oauth-protected-resource":
        return _r(200, {"resource": f"{o}/_emdash/api/mcp", "authorization_servers": [f"{o}/_emdash"]})
    if ruta == "/.well-known/oauth-authorization-server/_emdash":
        return _r(200, {"issuer": f"{o}/_emdash", "token_endpoint": f"{o}/_emdash/api/oauth/token",
                        "registration_endpoint": f"{o}/_emdash/api/oauth/register",
                        "device_authorization_endpoint": f"{o}/_emdash/api/oauth/device/code",
                        "grant_types_supported": ["authorization_code", "refresh_token", "urn:ietf:params:oauth:grant-type:device_code"]})
    if ruta == "/_emdash/api/oauth/register":
        e["registros"] = e.get("registros", 0) + 1; e["scope_registro"] = datos.get("scope"); _g(e)
        return _r(201, {"client_id": "cli-1"})
    if ruta == "/_emdash/api/oauth/device/code":
        if e.get("_form"):   # como EmDash: este punto solo acepta JSON, y envuelve la respuesta
            return _r(400, {"success": False, "error": {"code": "INVALID_REQUEST", "message": "Request body must be valid JSON"}})
        if datos.get("client_id") != "cli-1" or "admin" in datos.get("scope", ""):
            return _r(400, {"error": "invalid_request"})
        e["scope_pedido"] = datos.get("scope"); e["recurso_pedido"] = datos.get("resource"); _g(e)
        return _r(200, {"success": True, "data": {"device_code": "dev-secreto", "user_code": "ABCD-EFGH",
                        "verification_uri": f"{o}/_emdash/device", "expires_in": 600, "interval": 0}})
    if ruta == "/_emdash/api/oauth/token":
        if datos.get("grant_type") == "urn:ietf:params:oauth:grant-type:device_code" and datos.get("device_code") == "dev-secreto":
            if e["pendientes"] > 0:
                e["pendientes"] -= 1; _g(e)
                return _r(400, {"error": "authorization_pending"})
            e["tokens"] += 1; _g(e)
            return _r(200, {"access_token": f"tok{e['tokens']}", "expires_in": 3600, "refresh_token": "ref-1", "scope": datos.get("scope", "content:read content:write")})
        if datos.get("grant_type") == "refresh_token":
            esperado = e.get("refresco", "ref-1")
            if e["revocado"] or datos.get("refresh_token") != esperado or datos.get("client_id") != "cli-1":
                return _r(400, {"error": "invalid_grant"})
            e["tokens"] += 1; e["refresco"] = f"ref-{e['tokens']}"; _g(e)   # rota
            return _r(200, {"access_token": f"tok{e['tokens']}", "expires_in": 3600, "refresh_token": e["refresco"]})
        return _r(400, {"error": "unsupported_grant_type"})
    if ruta == "/_emdash/api/mcp":
        return pedir(metodo, "https://web.test/mcp", datos, cab)
    return 404, {}, "no"


def pedir(metodo, url, datos, cab, form=False):
    e = _e()
    if urllib.parse.urlsplit(url).netloc == "oauth.test":
        e["_form"] = bool(form)
        return _oauth(metodo, url, datos, cab, e)
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
            elif p["name"] == "articulos":
                res = {"datos": e.get("articulos", [])}
            elif p["name"] == "despublicar_articulo":
                a = p["arguments"]
                if a.get("confirmar") is not True:   # como el real: lo destructivo pide confirmar: true
                    return _r(200, {"jsonrpc": "2.0", "id": datos["id"], "result": {"isError": True, "content": [{"type": "text", "text": "Input validation error: confirmar"}]}})
                for x in e.get("articulos", []):
                    if x["id"] == a.get("articulo"):
                        x["status"] = "draft"
                _g(e)
                res = {"ok": True}
            elif p["name"] in ("content_get", "content_update"):   # como EmDash: _rev obligatorio, solo seo
                a = p["arguments"]
                it = next((x for x in e.get("contenido", []) if x["collection"] == a.get("collection") and a.get("id") in (x["id"], x["slug"])), None)
                if not it:
                    return _r(200, {"jsonrpc": "2.0", "id": datos["id"], "result": {"isError": True, "content": [{"type": "text", "text": "[NOT_FOUND] Content item not found"}]}})
                if p["name"] == "content_update":
                    if a.get("_rev") != f"rev{it['version']}" or it["id"] in e.get("falla_update", []):
                        return _r(200, {"jsonrpc": "2.0", "id": datos["id"], "result": {"isError": True, "content": [{"type": "text", "text": "[CONFLICT] rev"}]}})
                    it["seo"].update(a.get("seo") or {}); it["version"] += 1; _g(e)
                res = {"item": {k: it[k] for k in ("id", "slug", "status", "seo")}, "_rev": f"rev{it['version']}"}
            elif p["name"] == "embudo":
                res = {"months": [{"month": "2026-10", "visits": 10, "downloads": 1, "checkouts": 0, "sales": 0},
                                  {"month": "2026-11", "visits": 425, "downloads": 3, "checkouts": 2, "sales": 1}]}
            else:
                res = {"posts": {"published": 8}, "months": [{"month": "2026-11", "visits": 87, "buscadores": 5, "ia": 1}]}
            # como el servidor real: el resultado va como texto JSON, en un flujo SSE
            cuerpo = json.dumps({"jsonrpc": "2.0", "id": datos["id"], "result": {"content": [{"type": "text", "text": json.dumps(res)}]}})
            return 200, {"content-type": "text/event-stream"}, f"event: message\ndata: {cuerpo}\n\n"
    return 404, {}, "no"
