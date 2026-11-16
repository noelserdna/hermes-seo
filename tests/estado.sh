#!/usr/bin/env bash
# Estado real por turno (pre_llm_call): puertas con fecha y edad, en marcha, lo reciente, último informe de cada tipo,
# propuestas del parte; claves tapadas; vacío en cron; la cartera con todas las webs.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com --nombre "La Web" >/dev/null
python3 - "$P" <<'PY' && ok "turno: puertas con fecha y edad, aviso grave, informe con titular, propuestas, claves tapadas" || bad "turno"
import importlib.util, json, sys, time
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, C, E, PU, ES = m("hseo_base"), m("hseo_clientes"), m("hseo_encargos"), m("hseo_puertas"), m("hseo_estado")
g = PU.abrir("web", tipo="decision", titulo="📊 Una decisión", texto="x")["id"]
p = PU.leer(g); p["creada"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 3 * 86400)); p["revision"] = {"graves": 1}
B.escribir(PU.indice(g), p)
e = E.lanzar("web", "radar")
d = E.carpeta("web", e["id"]); (d / "radar.md").write_text("# Radar: 3 temas con demanda y uno caliente\n...")
e.update(estado="hecho", informe=True); E.guardar("web", e)
(C.carpeta("web") / "informes" / "partes").mkdir(parents=True)
(C.carpeta("web") / "informes" / "partes" / "ultimo.json").write_text(json.dumps({"fecha": "2026-11-16", "propuestas": [{"texto": "Nuevo título para X"}, {"texto": "clave ghp_" + "a" * 30}]}))
t = ES.turno("web")
assert "📊 Una decisión" in t and "hace 3 días" in t and "aviso grave" in t, t
assert "Radar: 3 temas con demanda" in t, t
assert "1. Nuevo título para X" in t and "[clave tapada]" in t and "ghp_" not in t, t
assert len(t) <= ES.MAX_WEB
c = ES.cartera(); assert "La Web: 1 puerta(s)" in c and "Disco" in c, c
assert "alta en curso" not in c
(C.carpeta("web") / "aterrizaje.json").write_text(json.dumps({"pasos": {"1": {"ok": True}, "5": {"ok": False, "detalle": "Google aún no tiene datos"}}, "lanzados": {}}))
(C.carpeta("web") / "aterrizaje.json").write_text(json.dumps({"pasos": {"1": {"ok": True}, "3": {"ok": False, "detalle": "falta decir cómo se publica"}, "5": {"ok": False, "detalle": "Google aún no tiene datos: no tienes que hacer nada"}}, "lanzados": {}}))
c = ES.cartera(); assert "🛬 alta en curso: 1 de 10; LE TOCA A LA PERSONA: 3. Cómo se publica" in c and "esperando: 5:" in c, c
PY
python3 - "$P" <<'PY' && ok "el hook: contexto en Telegram y CLI, nada en cron; en el encargado su web, en la coordinadora la cartera" || bad "hook"
import importlib.util, sys
from pathlib import Path
from types import SimpleNamespace as NS
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hermes_seo_plugin", P / "__init__.py"); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
hooks = {}
m.register(NS(profile_name="seo-p-web", register_hook=lambda n, f, **k: hooks.__setitem__(n, f),
              register_system_prompt_section=lambda *a, **k: None))
h = hooks["pre_llm_call"]
assert "Estado real de La Web" in h(platform="telegram")["context"]
assert "Estado real de La Web" in h(platform="cli")["context"]
assert h(platform="cron") is None
hooks.clear()
m.register(NS(profile_name="default", register_hook=lambda n, f, **k: hooks.__setitem__(n, f),
              register_telegram_handler=lambda f: None, register_command=lambda *a, **k: None,
              register_system_prompt_section=lambda *a, **k: None))
assert "cartera" in hooks["pre_llm_call"](platform="telegram")["context"]
PY
exit $fail
