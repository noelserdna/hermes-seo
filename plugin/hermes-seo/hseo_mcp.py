"""Cliente MCP de una web (su propio servidor MCP con OAuth), sin modelo. Sirve para publicar (adaptador «mcp» de
hseo_publicacion) y para leer sus datos (analítica, artículos…).

Dos formas de acceso, según lo que anuncie el servidor (nada de esto pasa por el chat ni por un modelo):
- Registro de agentes de auth.md («service_auth»): el sistema pide un código de 6 cifras para el correo de una persona
  con acceso al panel; esa persona lo aprueba en la web y el sistema guarda una «aserción» que renueva el token 90 días.
- OAuth 2.1 normal con flujo de dispositivo (RFC 8628; EmDash y cualquier MCP estándar): el sistema se registra como
  cliente (RFC 7591), pide un código, la persona entra en la web con la cuenta indicada y lo escribe; el sistema guarda
  el token de refresco y renueva solo. Pide solo los permisos de `capacidades.publicacion.permisos` (por defecto,
  leer y escribir contenido).

  hseo_mcp.py conectar <web> <correo>     pide el código y espera la aprobación en segundo plano (10 min)
  hseo_mcp.py estado <web>                conectado o no, y hasta cuándo
  hseo_mcp.py herramientas <web>          las herramientas que ofrece (las de escritura, marcadas)
  hseo_mcp.py llamar <web> <herramienta> ['{json}']   solo herramientas de lectura (escribir lo hace el notario)

La sesión vive en clientes/<web>/mcp-tokens/sesion.json (600; el guardia impide que un agente la lea).
cliente.json → capacidades.publicacion.url (o capacidades.mcp.url) es la dirección del servidor MCP.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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
Rechazo = B.Rechazo
UA = "hermes-seo/0.1 (mcp)"
PROTOCOLO = "2025-06-18"
GRANT_CLAIM = "urn:workos:agent-auth:grant-type:claim"
GRANT_JWT = "urn:ietf:params:oauth:grant-type:jwt-bearer"
GRANT_DISPOSITIVO = "urn:ietf:params:oauth:grant-type:device_code"
PERMISOS = "content:read content:write media:read mcp:tools"   # lo justo para SEO; nunca «admin» ni esquema


# ── dónde ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def url_mcp(slug: str) -> str:
    cap = C.leer(slug).get("capacidades") or {}
    u = ((cap.get("mcp") or {}).get("url") or (cap.get("publicacion") or {}).get("url") or "").strip()
    if not u.startswith("https://"):
        raise Rechazo(f"{slug} no tiene la dirección de su servidor MCP (capacidades.publicacion.url, https://…)")
    return u


def _origen(u: str) -> str:
    p = urllib.parse.urlsplit(u)
    return f"{p.scheme}://{p.netloc}"


def _dir(slug: str) -> Path:
    d = C.carpeta(slug) / "mcp-tokens"
    d.mkdir(parents=True, exist_ok=True)
    os.chmod(d, 0o700)
    return d


def _guardar(f: Path, datos: dict) -> None:
    B.escribir(f, datos)
    os.chmod(f, 0o600)


# ── HTTP ────────────────────────────────────────────────────────────────────────────────────────────────────────────
def _pedir(metodo: str, url: str, datos=None, cab: dict | None = None, form: bool = False, timeout: int = 60) -> tuple:
    """(código, cabeceras, cuerpo en texto). No lanza por códigos HTTP: quien llama decide."""
    if os.environ.get("HSEO_MCP_DOBLE"):   # pruebas: un módulo que hace de servidor
        return _cargar_doble().pedir(metodo, url, datos, cab or {}, form)
    h = {"User-Agent": UA, **(cab or {})}
    cuerpo = None
    if datos is not None:
        if form:
            cuerpo = urllib.parse.urlencode(datos).encode()
            h["Content-Type"] = "application/x-www-form-urlencoded"
        else:
            cuerpo = json.dumps(datos).encode()
            h.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url, data=cuerpo, method=metodo, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, {k.lower(): v for k, v in r.headers.items()}, r.read().decode(errors="replace")
    except urllib.error.HTTPError as e:
        return e.code, {k.lower(): v for k, v in (e.headers or {}).items()}, e.read().decode(errors="replace")
    except OSError as e:
        raise Rechazo(f"No pude hablar con {urllib.parse.urlsplit(url).netloc}: {e}")


def _cargar_doble():
    spec = importlib.util.spec_from_file_location("hseo_mcp_doble", os.environ["HSEO_MCP_DOBLE"])
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _json(texto: str) -> dict:
    try:
        d = json.loads(texto or "{}")
        return d if isinstance(d, dict) else {"datos": d}
    except ValueError:
        return {}


def _servidor_auth(u: str) -> tuple:
    """(metadatos del servidor de autorización, recurso protegido): RFC 9728 → RFC 8414; si no, el origen."""
    o = _origen(u)
    c, _, t = _pedir("GET", f"{o}/.well-known/oauth-protected-resource")
    pr = _json(t) if c == 200 else {}
    for emisor in (pr.get("authorization_servers") or []) + [o]:
        p = urllib.parse.urlsplit(emisor)
        base, ruta = f"{p.scheme}://{p.netloc}", p.path.rstrip("/")
        for cand in ([f"{base}/.well-known/oauth-authorization-server{ruta}"] if ruta else []) + [f"{base}/.well-known/oauth-authorization-server"]:
            c, _, t = _pedir("GET", cand)
            m = _json(t) if c == 200 else {}
            if m.get("token_endpoint") or m.get("agent_auth"):
                return m, pr.get("resource") or u
    return {}, pr.get("resource") or u


def metadatos(slug: str) -> dict:
    u = url_mcp(slug)
    o = _origen(u)
    m, recurso = _servidor_auth(u)
    aa = m.get("agent_auth") or {}
    return {"token": m.get("token_endpoint") or f"{o}/oauth/token",
            "identidad": aa.get("identity_endpoint") or aa.get("registration_endpoint") or f"{o}/agent/identity",
            "tipos": aa.get("identity_types_supported") or ([] if m.get("device_authorization_endpoint") else ["service_auth"]),
            "dispositivo": m.get("device_authorization_endpoint", ""), "registro": m.get("registration_endpoint", ""),
            "recurso": recurso}


def _permisos(slug: str) -> str:
    cap = C.leer(slug).get("capacidades") or {}
    return str(((cap.get("publicacion") or {}).get("permisos")) or PERMISOS)


# ── acceso ──────────────────────────────────────────────────────────────────────────────────────────────────────────
def conectar(slug: str, correo: str, esperar_aparte: bool = True) -> dict:
    """Pide el código para `correo` (que ya debe tener acceso al panel de la web) y deja esperando la aprobación."""
    correo = correo.strip().lower()
    if "@" not in correo:
        raise Rechazo("Hace falta el correo de una persona con acceso al panel de la web")
    m = metadatos(slug)
    nombre = f"hermes-seo · {C.leer(slug).get('nombre') or slug}"
    if "service_auth" not in m["tipos"] and "identity_assertion" not in m["tipos"]:
        if m["dispositivo"]:
            return _conectar_dispositivo(slug, correo, m, nombre, esperar_aparte)
        raise Rechazo("Ese servidor no admite ni el registro de agentes de auth.md ni el flujo de dispositivo de OAuth")
    c, _, t = _pedir("POST", m["identidad"], {"type": "service_auth", "login_hint": correo, "agent_name": nombre})
    r = _json(t)
    if c >= 300 or not r.get("claim_token"):
        raise Rechazo(f"El registro no funcionó ({c}): {(r.get('error_description') or r.get('error') or t)[:200]}")
    claim = r.get("claim") or {}
    _guardar(_dir(slug) / "pendiente.json", {"claim_token": r["claim_token"], "correo": correo, "token_url": m["token"],
                                             "creado": time.time(), "expira": time.time() + int(claim.get("expires_in") or 600),
                                             "intervalo": int(claim.get("interval") or 5)})
    if esperar_aparte:
        subprocess.Popen(B.desacoplar([sys.executable, str(Path(__file__)), "esperar", slug]), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"codigo": claim.get("user_code"), "donde": claim.get("verification_uri"), "minutos": int(claim.get("expires_in") or 600) // 60,
            "correo": correo}


def _cliente_oauth(slug: str, m: dict, nombre: str) -> str:
    """El client_id de hermes-seo en ese servidor (registro dinámico, una vez; se reutiliza)."""
    f = _dir(slug) / "cliente-oauth.json"
    cli = B.leer(f) or {}
    if cli.get("client_id") and cli.get("registro") == m["registro"]:
        return cli["client_id"]
    if not m["registro"]:
        raise Rechazo("El servidor no permite registrar clientes (sin registration_endpoint)")
    c, _, t = _pedir("POST", m["registro"], {"client_name": nombre, "grant_types": [GRANT_DISPOSITIVO, "refresh_token"],
                                              "token_endpoint_auth_method": "none", "redirect_uris": ["http://127.0.0.1/callback"],
                                              "response_types": ["code"], "scope": _permisos(slug)})
    r = _json(t)
    if c >= 300 or not r.get("client_id"):
        raise Rechazo(f"El registro del cliente OAuth no funcionó ({c}): {(r.get('error_description') or r.get('error') or t)[:200]}")
    _guardar(f, {"client_id": r["client_id"], "registro": m["registro"], "creado": B.ahora()})
    return r["client_id"]


def _conectar_dispositivo(slug: str, correo: str, m: dict, nombre: str, esperar_aparte: bool) -> dict:
    cid = _cliente_oauth(slug, m, nombre)
    c, _, t = _pedir("POST", m["dispositivo"], {"client_id": cid, "scope": _permisos(slug), "resource": m["recurso"]}, form=True)
    r = _json(t)
    if c >= 300 or not r.get("device_code") or not r.get("user_code"):
        raise Rechazo(f"El servidor no dio el código de dispositivo ({c}): {(r.get('error_description') or r.get('error') or t)[:200]}")
    _guardar(_dir(slug) / "pendiente.json", {"tipo": "dispositivo", "device_code": r["device_code"], "client_id": cid,
                                             "recurso": m["recurso"], "correo": correo, "token_url": m["token"],
                                             "creado": time.time(), "expira": time.time() + int(r.get("expires_in") or 600),
                                             "intervalo": int(r.get("interval") or 5)})
    if esperar_aparte:
        subprocess.Popen(B.desacoplar([sys.executable, str(Path(__file__)), "esperar", slug]), start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"codigo": r["user_code"], "donde": r.get("verification_uri_complete") or r.get("verification_uri"),
            "minutos": int(r.get("expires_in") or 600) // 60, "correo": correo}


def esperar(slug: str, tope_s: int = 900) -> str:
    """Sondea el token hasta que la persona apruebe, caduque o pasen tope_s segundos."""
    f = _dir(slug) / "pendiente.json"
    p = B.leer(f)
    if not p:
        return "no hay ninguna conexión pendiente"
    fin = min(p["expira"] + 30, time.time() + tope_s)

    marca = "device_code" if p.get("tipo") == "dispositivo" else "claim_token"

    def soltar():   # solo la petición propia: si alguien pidió otro código, ese fichero ya es de otra espera
        if (B.leer(f) or {}).get(marca) == p[marca]:
            f.unlink(missing_ok=True)

    while time.time() < fin:
        if p.get("tipo") == "dispositivo":
            pedido = {"grant_type": GRANT_DISPOSITIVO, "device_code": p["device_code"], "client_id": p["client_id"],
                      "resource": p["recurso"]}
        else:
            pedido = {"grant_type": GRANT_CLAIM, "claim_token": p["claim_token"]}
        c, _, t = _pedir("POST", p["token_url"], pedido, form=True)
        r = _json(t)
        if c == 200 and r.get("access_token"):
            _sesion(slug, r, p["correo"], p["token_url"],
                    {"client_id": p["client_id"], "recurso": p["recurso"]} if p.get("tipo") == "dispositivo" else None)
            soltar()
            _anotar(slug, "conectado", p["correo"], r.get("scope", ""))
            return "conectado"
        err = r.get("error", "")
        if err not in ("authorization_pending", "slow_down"):
            soltar()
            _anotar(slug, "fallido", p["correo"], err or str(c))
            return f"no se conectó: {err or c}"
        time.sleep(p.get("intervalo", 5) + (5 if err == "slow_down" else 0))
    soltar()
    _anotar(slug, "caducado", p["correo"], "")
    return "caducó sin aprobar: vuelve a pedir el código"


def _sesion(slug: str, r: dict, correo: str, token_url: str, previa: dict | None = None) -> dict:
    s = dict(previa or {})
    s.update(access_token=r["access_token"], expira=time.time() + int(r.get("expires_in") or 3600), correo=correo,
             token_url=token_url, scope=r.get("scope", s.get("scope", "")))
    if r.get("identity_assertion"):
        s.update(assertion=r["identity_assertion"], assertion_expira=time.time() + 90 * 86400)
    if r.get("refresh_token"):   # OAuth normal: el de refresco puede rotar en cada renovación
        s.update(refresh_token=r["refresh_token"], refresco_renovado=time.time())
    _guardar(_dir(slug) / "sesion.json", s)
    return s


def _anotar(slug: str, que: str, correo: str, detalle: str) -> None:
    B.anotar(C.carpeta(slug) / "config.jsonl", {"ts": B.ahora(), "quien": "hseo_mcp", "accion": f"mcp-{que}",
                                                "correo": correo, "detalle": detalle})


def token(slug: str) -> str:
    s = B.leer(_dir(slug) / "sesion.json")
    if not s:
        raise Rechazo(f"{C.leer(slug).get('nombre') or slug} no está conectada a su servidor MCP (hseo mcp conectar)")
    if s.get("expira", 0) - time.time() > 60:
        return s["access_token"]
    if s.get("refresh_token"):
        pedido = {"grant_type": "refresh_token", "refresh_token": s["refresh_token"], "client_id": s.get("client_id", "")}
        if s.get("recurso"):
            pedido["resource"] = s["recurso"]
    elif s.get("assertion"):
        pedido = {"grant_type": GRANT_JWT, "assertion": s["assertion"]}
    else:
        raise Rechazo("El acceso caducó y no hay con qué renovarlo: vuelve a conectar (hseo mcp conectar)")
    c, _, t = _pedir("POST", s["token_url"], pedido, form=True)
    r = _json(t)
    if c != 200 or not r.get("access_token"):
        if r.get("error") == "invalid_grant":
            _anotar(slug, "revocado", s.get("correo", ""), "")
            raise Rechazo("El acceso al servidor MCP de la web está revocado o caducado: vuelve a conectar (hseo mcp conectar)")
        raise Rechazo(f"No pude renovar el acceso al servidor MCP ({c}): {(r.get('error') or t)[:200]}")
    return _sesion(slug, r, s.get("correo", ""), s["token_url"], s)["access_token"]


def estado(slug: str) -> str:
    d = _dir(slug)
    if (d / "pendiente.json").exists():
        p = B.leer(d / "pendiente.json") or {}
        return f"⏳ esperando a que {p.get('correo')} apruebe el código (caduca en {max(0, int((p.get('expira', 0) - time.time()) / 60))} min)"
    s = B.leer(d / "sesion.json")
    if not s:
        return "❌ sin conectar"
    if s.get("refresh_token"):
        return f"✅ conectada como {s.get('correo')} (OAuth) · permisos: {s.get('scope') or '—'} · se renueva sola mientras se use"
    dias = int((s.get("assertion_expira", 0) - time.time()) / 86400)
    return f"✅ conectada como {s.get('correo')} · permisos: {s.get('scope') or '—'} · renovación válida {max(dias, 0)} días más"


# ── MCP (Streamable HTTP) ───────────────────────────────────────────────────────────────────────────────────────────
def _rpc(slug: str, metodo: str, params: dict | None = None) -> dict:
    url, tok = url_mcp(slug), token(slug)
    cab = {"Authorization": f"Bearer {tok}", "Accept": "application/json, text/event-stream"}
    c, h, t = _pedir("POST", url, {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                   "params": {"protocolVersion": PROTOCOLO, "capabilities": {},
                                              "clientInfo": {"name": "hermes-seo", "version": "0.1"}}}, cab)
    if c == 401:
        raise Rechazo("El servidor MCP rechazó el acceso (401): vuelve a conectar (hseo mcp conectar)")
    ini = _respuesta(t, h)
    if c >= 300 or "error" in ini:
        raise Rechazo(f"El servidor MCP no arrancó la sesión ({c}): {str(ini.get('error') or t)[:200]}")
    version = (ini.get("result") or {}).get("protocolVersion") or PROTOCOLO
    cab = {**cab, "MCP-Protocol-Version": version}
    if h.get("mcp-session-id"):
        cab["Mcp-Session-Id"] = h["mcp-session-id"]
    _pedir("POST", url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, cab)
    c, h2, t = _pedir("POST", url, {"jsonrpc": "2.0", "id": 2, "method": metodo, "params": params or {}}, cab, timeout=120)
    r = _respuesta(t, h2)
    if c >= 300 or "error" in r:
        raise Rechazo(f"El servidor MCP respondió con error ({c}): {str((r.get('error') or {}).get('message') or t)[:300]}")
    return r.get("result") or {}


def _respuesta(texto: str, cab: dict) -> dict:
    """JSON o flujo SSE (líneas «data: …»): devuelve el mensaje JSON-RPC con resultado o error."""
    if "text/event-stream" in (cab.get("content-type") or ""):
        for linea in texto.splitlines():
            if linea.startswith("data:"):
                d = _json(linea[5:].strip())
                if "result" in d or "error" in d:
                    return d
        return {}
    return _json(texto)


def herramientas(slug: str) -> list:
    return (_rpc(slug, "tools/list").get("tools") or [])


def _resultado(r: dict) -> dict:
    """De un tools/call: el contenido estructurado o el texto (JSON si lo es). Error de la herramienta → Rechazo."""
    texto = "\n".join(c.get("text", "") for c in r.get("content") or [] if c.get("type") == "text")
    if r.get("isError"):
        raise Rechazo(f"La web dijo que no: {texto[:400] or 'error sin detalle'}")
    if isinstance(r.get("structuredContent"), dict):
        return r["structuredContent"]
    d = _json(texto)
    return d or {"texto": texto}


def llamar(slug: str, herramienta: str, args: dict | None = None, escribir: bool = False) -> dict:
    """escribir=False (agentes, CLI): solo herramientas marcadas de lectura. El notario publica con escribir=True."""
    if not escribir:
        h = next((x for x in herramientas(slug) if x.get("name") == herramienta), None)
        if not h:
            raise Rechazo(f"El servidor MCP de la web no tiene la herramienta «{herramienta}»")
        if not (h.get("annotations") or {}).get("readOnlyHint"):
            raise Rechazo(f"«{herramienta}» cambia la web: eso solo pasa al aprobarse una puerta")
    return _resultado(_rpc(slug, "tools/call", {"name": herramienta, "arguments": args or {}}))


def main(argv=None) -> int:
    a = list(sys.argv[1:] if argv is None else argv)
    try:
        if a[:1] == ["conectar"] and len(a) == 3:
            r = conectar(a[1], a[2])
            print(f"🔑 Código {r['codigo']} para {r['correo']}: abre {r['donde']}, entra con ese correo y escríbelo "
                  f"(caduca en {r['minutos']} min). Lo espero solo; mira «hseo mcp estado {a[1]}».")
        elif a[:1] == ["esperar"] and len(a) == 2:
            print(esperar(a[1]))
        elif a[:1] == ["estado"] and len(a) == 2:
            print(estado(a[1]))
        elif a[:1] == ["herramientas"] and len(a) == 2:
            for h in herramientas(a[1]):
                an = h.get("annotations") or {}
                marca = "lectura" if an.get("readOnlyHint") else ("⚠️ destructiva" if an.get("destructiveHint") else "escribe")
                print(f"{h.get('name'):28} {marca:14} {(h.get('title') or h.get('description') or '')[:80]}")
        elif a[:1] == ["llamar"] and len(a) in (3, 4):
            print(json.dumps(llamar(a[1], a[2], json.loads(a[3]) if len(a) == 4 else {}), ensure_ascii=False, indent=1)[:20000])
        else:
            print(__doc__, file=sys.stderr)
            return 2
    except Rechazo as e:
        print(f"⛔ {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
