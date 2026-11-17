"""API de la pestaña SEO con un panel falso (sesión inyectada): identidad, webs, puertas (solo lectura), métricas, cambios."""
import importlib.util, json, os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
T = Path(tempfile.mkdtemp()); os.environ.update(HERMES_SEO_HOME=str(T / "home"), HERMES_SEO_DESHACER_S="60")
spec = importlib.util.spec_from_file_location("hseo_dashboard", ROOT / "plugin/hermes-seo/dashboard/plugin_api.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
fallos = 0
def ok(c, t):
    global fallos
    print(("ok   " if c else "FAIL ") + t); fallos += (not c)

SESION = {"email": "ana@ejemplo.com"}
app = FastAPI(); app.include_router(m.router, prefix="/api/plugins/hermes-seo")
@app.middleware("http")
async def sesion(request: Request, call_next):
    if SESION.get("email"):
        request.state.session = NS(email=SESION["email"], user_id="u1", provider="test")
    return await call_next(request)
cli = TestClient(app); A = "/api/plugins/hermes-seo"
m.C.alta("web", "web.com", nombre="La Web")
(T / "home/aprobadores.json").write_text(json.dumps({"ana": {"nombre": "Ana", "canales": {"dashboard": "ana@ejemplo.com"}, "clientes": ["*"]}}))
g = m.PU.abrir("web", tipo="decision", titulo="📊 Métricas", texto="3 propuestas")["id"]

SESION["email"] = "otro@ejemplo.com"
ok(cli.get(A + "/webs").status_code == 403, "quien no está en aprobadores no entra")
SESION["email"] = None
ok(cli.get(A + "/webs").status_code == 403, "sin sesión (y sin modo local) no entra")
SESION["email"] = "ana@ejemplo.com"
w = cli.get(A + "/webs").json()
ok(w[0]["nombre"] == "La Web" and w[0]["puertas"] == 1 and "jev" not in w[0], "la cartera con sus puertas")
ps = cli.get(A + "/puertas").json()
ok(len(ps) == 1 and ps[0]["opciones"][0]["verbo"] == "acepto", "las puertas pendientes con sus opciones")
ok(cli.post(A + f"/decidir/{g}", json={"verbo": "acepto"}).status_code in (404, 405), "el panel no decide (no hay /decidir)")
ok(cli.post(A + f"/deshacer/{g}").status_code in (404, 405), "ni deshace")
ok(m.PU.leer(g)["estado"] == "abierta", "la puerta sigue abierta")
ok(cli.get(A + "/metricas/web").json() == {"hay_datos": False}, "métricas sin datos: lo dice")
ok(cli.get(A + "/metricas/no-existe").status_code == 409, "métricas de una web que no existe: 409")
(T / "home/clientes/web/cambios.jsonl").write_text(json.dumps({"id": "c-1", "ts": "2026-11-01T00:00:00Z", "clase": "articulo", "hipotesis": "h", "firma": "Ana"}) + "\n")
ok(cli.get(A + "/cambios/web").json()[0]["hipotesis"] == "h", "los cambios con su hipótesis")
# ── configuración: se ve entera, solo se cambia lo seguro, queda en el historial ──
c = cli.get(A + "/config/web").json()
ok(c["nombre"] == "La Web" and any(e["clave"] == "negocio.voz" for e in c["editables"]), "la configuración con sus campos editables")
ok(any(p["id"] == "articulo" and p["etapas"][1]["id"] == "redactar" for p in c["como_trabaja"]), "cómo trabaja: etapas de cada pipeline")
ok("secretos" not in json.dumps(c) and "TOKEN" not in json.dumps(c), "ninguna clave en la vista")
r = cli.post(A + "/config/web", json={"clave": "negocio.voz", "valor": "Cercana y clara"})
ok(r.status_code == 200 and m.C.leer("web")["negocio"]["voz"] == "Cercana y clara", "cambiar la voz")
ok(cli.post(A + "/config/web", json={"clave": "competidores", "valor": "a.com\nb.com\n"}).status_code == 200
   and m.C.leer("web")["competidores"] == ["a.com", "b.com"], "una lista, una línea por elemento")
ok(cli.post(A + "/config/web", json={"clave": "politicas.tope_semanal", "valor": "2"}).status_code == 200
   and m.C.leer("web")["politicas"]["tope_semanal"] == 2, "un número")
ok(cli.post(A + "/config/web", json={"clave": "capacidades.publicacion.adaptador", "valor": "mcp"}).status_code == 403, "cómo publica no se cambia desde el panel")
ok(cli.post(A + "/config/web", json={"clave": "contacto.correo", "valor": "x@y.com"}).status_code == 403, "el contacto tampoco")
ok(cli.post(A + "/config/web", json={"clave": "politicas.congelado_hasta", "valor": "mañana"}).status_code == 422, "fecha mal escrita: no")
ok(cli.post(A + "/config/web", json={"clave": "ia.motores", "valor": "inventado"}).status_code == 409, "lo que la validación rechaza no se guarda")
h = cli.get(A + "/config/web").json()["historial"]
ok(h and h[0]["quien"] == "panel:ana" and any(x["clave"] == "negocio.voz" for x in h), "queda en el historial con quién")
SESION["email"] = "otro@ejemplo.com"
ok(cli.post(A + "/config/web", json={"clave": "negocio.voz", "valor": "x"}).status_code == 403, "quien no está en aprobadores no cambia nada")
SESION["email"] = "ana@ejemplo.com"

sys.exit(1 if fallos else 0)
