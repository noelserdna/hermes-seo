#!/usr/bin/env bash
# Correo (lado del plugin, con un Worker de mentira en una carpeta): contacto único, puerta con códigos y botones,
# decidir SOLO por código (remitente de esa web, código de una puerta suya, contenido sin cambios), deshacer,
# «cambios» sin motivo, «sí» suelto = petición al encargado, remitente ajeno descartado, propuesta del parte.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'sleep 1; rm -rf "$T" 2>/dev/null' EXIT
export HERMES_SEO_HOME="$T/home" HOME="$T/casa" FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
export HSEO_EJECUTORES="$ROOT/tests/dobles" HSEO_SIN_SCOPE=1
mkdir -p "$T/buzon" "$T/bin"; printf '#!/usr/bin/env bash\necho "$*" >> "$FALSO_LLAMADAS"\ncase "$*" in *" chat "*) echo "Respuesta del encargado"; echo "session_id: x";; *) "%s" "$@";; esac\n' "$ROOT/tests/dobles/hermes" > "$T/bin/hermes"; chmod +x "$T/bin/hermes"
export HERMES_BIN="$T/bin/hermes" HSEO_CORREO_URL="file://$T/buzon" HSEO_CORREO_SECRETO=x HSEO_CORREO_BUZON=hermes_seo@x.dev
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com >/dev/null; python3 "$P/hseo_clientes.py" alta otra otra.com >/dev/null
echo '{}' > "$HERMES_SEO_HOME/aprobadores.json"
python3 - "$P" "$T" <<'PY' && ok "contacto único entre webs, nunca el buzón; el dueño queda como aprobador de su web por correo" || bad "contacto"
import importlib.util, json, sys
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, HC = m("hseo_base"), m("hseo_correo")
HC.poner_contacto("web", "Ana@Gmail.com", "correo")
def rechaza(f):
    try: f(); return False
    except B.Rechazo: return True
assert rechaza(lambda: HC.poner_contacto("otra", "ana@gmail.com"))
assert rechaza(lambda: HC.poner_contacto("otra", "hermes_seo@x.dev"))
assert rechaza(lambda: HC.poner_contacto("otra", "noreply@x.com"))
HC.poner_contacto("otra", "bob@otra.com", "ambos")
ap = json.loads((B.home() / "aprobadores.json").read_text())
assert ap["contacto-web"]["canales"]["email"] == "ana@gmail.com" and ap["contacto-web"]["clientes"] == ["web"]
assert HC.por_correo("web") and not HC.por_telegram("web") and HC.por_correo("otra") and HC.por_telegram("otra")
PY
python3 - "$P" "$T" <<'PY' && ok "puerta: correo con texto y botones mailto con código; decidir por código; confirmación con DESHACER" || bad "puerta por correo"
import importlib.util, json, sys, re
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, PU, HC = m("hseo_base"), m("hseo_puertas"), m("hseo_correo")
g = PU.abrir("web", tipo="decision", titulo="📊 Una decisión", texto="Texto legible de lo que se decide")["id"]
PU.marcar(g, correo=HC.enviar_puerta(PU.leer(g))); HC.despachar()
env = [json.loads(l) for l in (T / "buzon/enviados.jsonl").read_text().splitlines()]
e = env[-1]; cod = PU.leer(g)["correo"]["codigos"]
assert e["to"] == "ana@gmail.com" and "Texto legible" in e["text"] and f"APROBAR%20{cod['acepto']}" in e["html"] and "mailto:hermes_seo@x.dev" in e["html"], e
pend = lambda *ms: (T / "buzon/pendientes.json").write_text(json.dumps(list(ms)))
pend({"id": "1", "de": "ana@gmail.com", "asunto": "sí", "texto": "sí, adelante", "message_id": "<a@g>"})
HC.recoger(); assert PU.leer(g)["estado"] == "abierta"                                   # un «sí» suelto no decide
pend({"id": "2", "de": "intruso@x.com", "asunto": f"APROBAR {cod['acepto']}", "texto": f"APROBAR {cod['acepto']}", "message_id": "<b@x>"})
HC.recoger(); assert PU.leer(g)["estado"] == "abierta"                                   # remitente ajeno
pend({"id": "3", "de": "bob@otra.com", "asunto": f"APROBAR {cod['acepto']}", "texto": f"APROBAR {cod['acepto']}", "message_id": "<c@x>"})
HC.recoger(); assert PU.leer(g)["estado"] == "abierta"                                   # código de otra web
pend({"id": "4", "de": "ana@gmail.com", "asunto": f"APROBAR {cod['acepto']}",
      "texto": f"APROBAR {cod['acepto']}\n\nEl lun, 16 nov 2026 a las 10:00, hermes escribió:\n> DESCARTAR {cod['rechazo']}", "message_id": "<d@g>"})
HC.recoger(); p = PU.leer(g)
assert p["estado"] == "decidida" and p["decision"]["verbo"] == "acepto" and p["decision"]["actor"]["canal"] == "email"
import time; assert p["firmar_en"] - time.time() > 1500                                # ventana de 30 min por correo
HC.despachar(); conf = json.loads((T / "buzon/enviados.jsonl").read_text().splitlines()[-1])
assert conf["in_reply_to"] == "<d@g>" and f"DESHACER {cod['deshacer']}" in conf["text"]
pend({"id": "5", "de": "ana@gmail.com", "asunto": "x", "texto": f"DESHACER {cod['deshacer']}", "message_id": "<e@g>"})
HC.recoger(); p = PU.leer(g); assert p["estado"] == "abierta" and not p.get("correo")     # deshecha: se reenviará
PY
python3 - "$P" "$T" <<'PY' && ok "contenido cambiado: no decide y se reenvía; CAMBIOS sin motivo: se pide; con motivo: decide" || bad "hash y cambios"
import importlib.util, json, sys
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, PU, HC = m("hseo_base"), m("hseo_puertas"), m("hseo_correo")
g = PU.abrir("web", tipo="decision", titulo="📊 Otra", texto="v1")["id"]
PU.marcar(g, correo=HC.enviar_puerta(PU.leer(g))); cod = PU.leer(g)["correo"]["codigos"]
p = PU.leer(g); p["texto"] = "v2"; B.escribir(PU.indice(g), p)
pend = lambda *ms: (T / "buzon/pendientes.json").write_text(json.dumps(list(ms)))
pend({"id": "6", "de": "ana@gmail.com", "asunto": "x", "texto": f"APROBAR {cod['acepto']}", "message_id": "<f@g>"})
HC.recoger(); assert PU.leer(g)["estado"] == "abierta" and not PU.leer(g).get("correo")
PU.marcar(g, correo=HC.enviar_puerta(PU.leer(g))); cod = PU.leer(g)["correo"]["codigos"]
pend({"id": "7", "de": "ana@gmail.com", "asunto": "x", "texto": f"CAMBIOS {cod['cambios']}", "message_id": "<g@g>"})
HC.recoger(); assert PU.leer(g)["estado"] == "abierta"
r = [json.loads(l) for l in (B.home() / "correo/recibidos.jsonl").read_text().splitlines()][-1]; assert "se pide" in r["resultado"], r
pend({"id": "8", "de": "ana@gmail.com", "asunto": "x", "texto": f"CAMBIOS {cod['cambios']}: menos tecnicismos", "message_id": "<h@g>"})
HC.recoger(); p = PU.leer(g); assert p["estado"] == "decidida" and p["decision"]["texto"] == "menos tecnicismos", p.get("decision")
PY
python3 - "$P" "$T" <<'PY' && ok "botón de un correo viejo: no decide, y se contesta cuál vale; cada puerta con su asunto" || bad "código viejo"
import importlib.util, json, sys
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, PU, HC = m("hseo_base"), m("hseo_puertas"), m("hseo_correo")
HC.despachar()
g1 = PU.abrir("web", tipo="decision", titulo="📊 Lección", texto="v1")["id"]
PU.marcar(g1, correo=HC.enviar_puerta(PU.leer(g1))); viejo = PU.leer(g1)["correo"]["codigos"]["rechazo"]
p = PU.leer(g1); p["encargo"] = "enc-1"; p["estado"] = "firmada"; B.escribir(PU.indice(g1), p)   # se pidieron cambios
g2 = PU.abrir("web", tipo="decision", titulo="📊 Lección", texto="v2")["id"]
p = PU.leer(g2); p["encargo"] = "enc-1"; B.escribir(PU.indice(g2), p)
PU.marcar(g2, correo=HC.enviar_puerta(PU.leer(g2))); HC.despachar()
(T / "buzon/pendientes.json").write_text(json.dumps([{"id": "v1", "de": "ana@gmail.com", "asunto": f"DESCARTAR {viejo}", "texto": f"DESCARTAR {viejo}", "message_id": "<v@g>"}]))
HC.recoger(); HC.despachar()
assert PU.leer(g2)["estado"] == "abierta"
env = [json.loads(l) for l in (T / "buzon/enviados.jsonl").read_text().splitlines()]
r = env[-1]; assert r["in_reply_to"] == "<v@g>" and "ya no vale" in r["text"] and "versión vigente" in r["text"], r
asuntos = [e["subject"] for e in env if e["subject"].startswith("🚪 📊 Lección")]
assert len(asuntos) == 2 and all(" · " in a for a in asuntos), asuntos
PY
python3 - "$P" "$T" <<'PY' && ok "tope diario: solo frena textos libres; un código válido decide igual" || bad "tope diario"
import importlib.util, json, sys, time
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, PU, HC = m("hseo_base"), m("hseo_puertas"), m("hseo_correo")
HC.despachar()
f = B.home() / "correo/recibidos.jsonl"; antes = f.read_text() if f.exists() else ""
hoy = time.strftime("%Y-%m-%d")
f.write_text(antes + "".join(json.dumps({"ts": f"{hoy}T01:00:00Z", "web": "web", "resultado": r}, ensure_ascii=False) + "\n"
                             for r in ["descartado: código desconocido"] * 12))
g = PU.abrir("web", tipo="decision", titulo="📊 Tope", texto="t")["id"]
PU.marcar(g, correo=HC.enviar_puerta(PU.leer(g))); c = PU.leer(g)["correo"]["codigos"]["rechazo"]
(T / "buzon/pendientes.json").write_text(json.dumps([{"id": "t1", "de": "ana@gmail.com", "asunto": f"DESCARTAR {c}", "texto": f"DESCARTAR {c}", "message_id": "<t@g>"}]))
HC.recoger(); HC.despachar()
assert PU.leer(g)["estado"] == "decidida", PU.leer(g)["estado"]
f.write_text(antes + "".join(json.dumps({"ts": f"{hoy}T01:00:00Z", "web": "web", "resultado": "petición al encargado"}, ensure_ascii=False) + "\n" for _ in range(10)))
assert HC.procesar({"id": "t2", "de": "ana@gmail.com", "asunto": "hola", "texto": "una duda"}) == "descartado: tope diario"
f.write_text(antes)
PY
python3 - "$P" "$T" <<'PY' && ok "texto libre: el encargado contesta en el mismo hilo (sesión «correo»)" || bad "texto libre"
import importlib.util, json, sys, time
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, HC = m("hseo_base"), m("hseo_correo")
HC.despachar()
(T / "buzon/pendientes.json").write_text(json.dumps([{"id": "9", "de": "ana@gmail.com", "asunto": "Una duda", "texto": "¿cómo va la web?", "message_id": "<i@g>"}]))
HC.recoger()
e = {}
for _ in range(100):   # la respuesta del encargado llega desacoplada: se espera la que va en ESTE hilo
    HC.despachar()
    e = next((json.loads(l) for l in (T / "buzon/enviados.jsonl").read_text().splitlines() if '"<i@g>"' in l), {})
    if e: break
    time.sleep(0.1)
assert e["text"] == "Respuesta del encargado" and e["in_reply_to"] == "<i@g>" and e["subject"] == "Re: Una duda", e
assert "-c correo" in (T / "llamadas").read_text()
PY
python3 "$P/hseo_clientes.py" alta tercera tercera.com >/dev/null
python3 - "$P" "$T" <<'PY' && ok "contacto nuevo: correo de confirmación; la misma dirección ya comprobada no lo repite ni pierde la comprobación" || bad "confirmación"
import importlib.util, json, sys
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, C, HC = m("hseo_base"), m("hseo_clientes"), m("hseo_correo")
HC.despachar()
r = HC.poner_contacto("tercera", "eva@tercera.com", "correo")
assert "confirmación enviado" in r, r
HC.despachar()
env = [json.loads(l) for l in (T / "buzon/enviados.jsonl").read_text().splitlines()]
assert env[-1]["to"] == "eva@tercera.com" and env[-1]["subject"].startswith("📧 Confirma tu correo"), env[-1]
cfg = C.leer("tercera"); cfg["contacto"]["verificado"] = "2026-11-16T10:00:00Z"; C._guardar("tercera", cfg)
r = HC.poner_contacto("tercera", "eva@tercera.com", "ambos")
assert "confirmación" not in r and C.leer("tercera")["contacto"].get("verificado"), r
PY
python3 "$P/hseo_clientes.py" alta etiq etiq.com >/dev/null
python3 - "$P" "$T" <<'PY' && ok "contacto con etiqueta (ana+web@…): Gmail responde desde ana@…; el hilo y el código dicen de qué web es" || bad "etiqueta"
import importlib.util, json, sys
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, C, HC, PU = m("hseo_base"), m("hseo_clientes"), m("hseo_correo"), m("hseo_puertas")
HC.despachar()
HC.poner_contacto("etiq", "ana+etiq@gmail.com", "correo"); HC.despachar()
conf = [json.loads(l) for l in (T / "buzon/enviados.jsonl").read_text().splitlines()][-1]
mid = json.loads((B.home() / "correo/enviados.jsonl").read_text().splitlines()[-1])["message_id"]
# 1) responde a la confirmación desde la dirección principal: cuenta para «etiq», no para «web»
(T / "buzon/pendientes.json").write_text(json.dumps([{"id": "e1", "de": "ana@gmail.com", "asunto": "Re: Confirma", "texto": "ok", "message_id": "<r1@g>", "in_reply_to": mid}]))
HC.recoger(); HC.despachar()
assert C.leer("etiq")["contacto"].get("verificado"), "no se comprobó"
assert json.loads((B.home() / "correo/recibidos.jsonl").read_text().splitlines()[-1])["web"] == "etiq"
# 2) un botón de una puerta de «etiq», enviado desde la principal: decide
g = PU.abrir("etiq", tipo="decision", titulo="📊 Etiq", texto="t")["id"]
PU.marcar(g, correo=HC.enviar_puerta(PU.leer(g))); c = PU.leer(g)["correo"]["codigos"]["rechazo"]
(T / "buzon/pendientes.json").write_text(json.dumps([{"id": "e2", "de": "ana@gmail.com", "asunto": f"DESCARTAR {c}", "texto": f"DESCARTAR {c}", "message_id": "<r2@g>"}]))
HC.recoger(); HC.despachar()
assert PU.leer(g)["estado"] == "decidida", PU.leer(g)["estado"]
# 3) un texto suelto desde la principal, sin hilo: es de la web con esa dirección exacta («web»)
assert HC._webs_de("ana@gmail.com") == (["web"], ["etiq"])
# 4) una dirección con etiqueta ajena no abre las demás
assert HC._webs_de("ana+otra@gmail.com") == ([], [])
PY
exit $fail
