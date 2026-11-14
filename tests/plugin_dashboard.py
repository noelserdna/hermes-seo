"""API de la pestaña SEO con un panel falso (sesión inyectada): identidad, webs, decidir y deshacer, métricas, cambios."""
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
ok(w[0]["nombre"] == "La Web" and w[0]["puertas"] == 1 and w[0]["jev"] == "humano", "la cartera con sus puertas y el modo de Jev")
ps = cli.get(A + "/puertas").json()
ok(len(ps) == 1 and ps[0]["opciones"][0]["verbo"] == "acepto", "las puertas pendientes con sus opciones")
r = cli.post(A + f"/decidir/{g}", json={"verbo": "rechazo", "texto": ""})
ok(r.status_code == 409 and "motivo" in r.json()["detail"], "rechazar sin motivo: 409 con el motivo")
r = cli.post(A + f"/decidir/{g}", json={"verbo": "acepto"}).json()
ok(r["estado"] == "decidida" and r["decidio"] == "ana", "decidir registra la decisión de la persona del panel")
p = m.PU.leer(g)
ok(p["decision"]["actor"]["canal"] == "dashboard" and p["decision"]["prueba"]["proveedor"] == "test", "canal dashboard con su prueba de sesión")
r = cli.post(A + f"/deshacer/{g}").json()
ok(r["estado"] == "abierta", "deshacer la reabre")
ok(cli.get(A + "/metricas/web").json() == {"hay_datos": False}, "métricas sin datos: lo dice")
ok(cli.get(A + "/metricas/no-existe").status_code == 409, "métricas de una web que no existe: 409")
(T / "home/clientes/web/cambios.jsonl").write_text(json.dumps({"id": "c-1", "ts": "2026-11-01T00:00:00Z", "clase": "articulo", "hipotesis": "h", "firma": "Ana"}) + "\n")
ok(cli.get(A + "/cambios/web").json()[0]["hipotesis"] == "h", "los cambios con su hipótesis")
sys.exit(1 if fallos else 0)
