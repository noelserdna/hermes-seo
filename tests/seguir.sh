#!/usr/bin/env bash
# Lo que la coordinadora promete para cuando se cierre una puerta: se apunta (hseo seguir) y, al cerrarse, el bucle de
# puertas le da un turno en su tema. Sin Hermes: gateway.session y gateway.wake son dobles que recogen el turno.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }
P="$ROOT/plugin/hermes-seo"
H="python3 $P/hseo_cli.py"
python3 "$P/hseo_clientes.py" alta web web.test --estado repo >/dev/null
mkdir -p "$HERMES_SEO_HOME/clientes/web/encargos/enc1"
echo '{"telegram_cartera":{"chat_id":"111","thread_id":"222"}}' > "$HERMES_SEO_HOME/seo.json"

no "no se apunta para un encargo que no existe" "$H seguir web nada 'avisar a Bing'"
no "ni para una web que no existe" "$H seguir otra enc1 'avisar a Bing'"
si "se apunta para un encargo" "$H seguir web enc1 avisar a Bing de los 23 enlaces | grep -q Apuntado"
si "sale en la lista y en el estado de cada turno de la coordinadora" \
  "$H seguimientos | grep -q 'avisar a Bing' && python3 -c \"import sys;sys.path.insert(0,'$P');import hseo_estado as E;assert 'avisar a Bing' in E.cartera()\""

python3 - "$P" <<'PY' && ok "espera mientras la puerta está abierta o se piden cambios; al firmarse, un turno en el tema de la coordinadora y se borra" || bad "aviso al cerrarse"
import asyncio, json, os, sys, types
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P.parent))
turnos = []
g = types.ModuleType("gateway"); gs = types.ModuleType("gateway.session"); gw = types.ModuleType("gateway.wake")
class SessionSource:
    def __init__(self, **kw): self.__dict__.update(kw)
async def deliver_wake(adapter, *, text, source=None, **kw):
    if adapter == "caido":
        raise RuntimeError("gateway caído")
    turnos.append((source.chat_id, source.thread_id, source.chat_type, text))
gs.SessionSource = SessionSource; gw.deliver_wake = deliver_wake
sys.modules.update({"gateway": g, "gateway.session": gs, "gateway.wake": gw})
import importlib.util
spec = importlib.util.spec_from_file_location("hermes_seo", P / "__init__.py", submodule_search_locations=[str(P)])
M = importlib.util.module_from_spec(spec); sys.modules["hermes_seo"] = M; spec.loader.exec_module(M)
PU = M._cargar("hseo_puertas"); S = M._cargar("hseo_seguir"); B = M._cargar("hseo_base")
class Adapter: platform = "telegram"
M._RT["adapter"] = Adapter()
enviados = []
class Bot:
    async def send_message(self, **kw): enviados.append(kw)
home = Path(os.environ["HERMES_SEO_HOME"])
def puerta(gid, estado, verbo=None, creada="2026-11-24T10:00:00Z", **extra):
    (home / "puertas").mkdir(exist_ok=True)
    p = {"id": gid, "cliente": "web", "encargo": "enc1", "tipo": "cambio-tecnico", "titulo": "🔧 Títulos", "estado": estado,
         "creada": creada, **({"decision": {"verbo": verbo}} if verbo else {}), **extra}
    (home / "puertas" / f"{gid}.json").write_text(json.dumps(p))
corre = lambda: asyncio.run(M._seguimientos(Bot()))
corre(); assert not turnos                                        # sin puerta aún
puerta("g6b0000000001", "abierta"); corre(); assert not turnos               # abierta: espera
puerta("g6b0000000001", "firmada", "cambios", resultado="cambios pedidos"); corre(); assert not turnos   # cambios: espera a la siguiente
puerta("g6b0000000002", "firmada", "acepto", creada="2026-11-24T11:00:00Z", resultado="MCP SEO: 12 de 12"); corre()
assert len(turnos) == 1, turnos
chat, hilo, tipo, texto = turnos[0]
assert (chat, hilo, tipo) == ("111", "222", "dm") and "avisar a Bing" in texto and "12 de 12" in texto and "automático" in texto
assert not S.pendientes()
# si el gateway no lo acepta, se reintenta; tras MAX_INTENTOS, al menos un mensaje en el tema
S.apuntar("web", "g6b0000000002", "pedir la indexación")
M._RT["adapter"] = "caido"
for _ in range(S.MAX_INTENTOS - 1):
    corre()
assert S.pendientes() and not enviados
corre()
assert not S.pendientes() and len(enviados) == 1 and "pedir la indexación" in enviados[0]["text"]
PY

python3 - "$P" <<'PY' && ok "con la puerta descartada o con error también avisa (para no hacerlo y explicarlo)" || bad "descartada/error"
import os, sys, json
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
import hseo_seguir as S
home = Path(os.environ["HERMES_SEO_HOME"])
(home / "puertas" / "g6b0000000003.json").write_text(json.dumps({"id": "g6b0000000003", "cliente": "web", "encargo": "enc1", "titulo": "x", "estado": "error",
                                                      "error": "la web dijo que no", "creada": "2026-11-24T12:00:00Z"}))
S.apuntar("web", "g6b0000000003", "avisar a Bing")
(s, p, fin), = S.listos()
assert "falló" in fin and "no lo hagas" in S.texto_aviso(s, p, fin)
PY
exit $fail
