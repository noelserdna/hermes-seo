#!/usr/bin/env bash
# Vigilancia sin IA: una incidencia → un intento de arreglo (sin aviso) → si sigue tras la espera, UN aviso con lo
# probado → al desaparecer, resuelta (sin mensaje, cuenta para el parte); las que no tienen arreglo avisan ya.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com --nombre "La Web" >/dev/null
python3 - "$P" <<'PY' && ok "parada: intento sin aviso → sigue → un aviso con lo probado → no se repite → resuelta sola no avisa" || bad "ciclo parada"
import importlib.util, sys, time
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, E, V = m("hseo_base"), m("hseo_encargos"), m("hseo_vigilancia")
e = E.lanzar("web", "radar"); e["estado"] = "parado"; E.guardar("web", e)
lanzados = []
t0 = time.time()
assert V.ciclo("web", t0, lanzar=lambda s, f: lanzados.append(f)) == [] and len(lanzados) == 1      # intenta, calla
assert V.ciclo("web", t0 + 60, lanzar=lambda s, f: lanzados.append(f)) == [] and len(lanzados) == 1  # espera
inc = B.leer(V._dir("web") / f"{lanzados[0]}.json"); inc["probado"] = "reintentada"; B.escribir(V._dir("web") / f"{lanzados[0]}.json", inc)
av = V.ciclo("web", t0 + 20 * 60, lanzar=lambda s, f: lanzados.append(f))
assert len(av) == 1 and "parado" in av[0] and "reintenté" in av[0] and "reintentada" in av[0], av
assert V.ciclo("web", t0 + 30 * 60, lanzar=lambda s, f: lanzados.append(f)) == []                   # no se repite
e["estado"] = "en-curso"; E.guardar("web", e)
assert V.ciclo("web", t0 + 40 * 60) == []
inc = B.leer(V._dir("web") / f"{lanzados[0]}.json"); assert inc["estado"] == "resuelta" and inc["sola"] is False
PY
python3 - "$P" <<'PY' && ok "sin arreglo posible (puerta con error): avisa en el primer ciclo, una vez" || bad "sin arreglo"
import importlib.util, sys, time
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, PU, V = m("hseo_base"), m("hseo_puertas"), m("hseo_vigilancia")
g = PU.abrir("web", tipo="decision", titulo="📊 X", texto="x")["id"]
p = PU.leer(g); p.update(estado="error", error="no se pudo"); B.escribir(PU.indice(g), p)
av = V.ciclo("web"); assert len(av) == 1 and "no se pudo completar" in av[0], av
assert V.ciclo("web") == []
PY
python3 - "$P" <<'PY' && ok "arreglo resuelto antes de la espera: ningún mensaje y cuenta como resuelta sola" || bad "resuelta sola"
import importlib.util, sys, time
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, E, V = m("hseo_base"), m("hseo_encargos"), m("hseo_vigilancia")
e = E.lanzar("web", "metricas-semanales") if False else E.lanzar("web", "revision-mensual")
e["estado"] = "parado"; E.guardar("web", e)
f = []
assert V.ciclo("web", lanzar=lambda s, x: f.append(x)) == []
e["estado"] = "en-curso"; E.guardar("web", e)
assert V.ciclo("web") == []
inc = B.leer(V._dir("web") / f"{f[0]}.json"); assert inc["estado"] == "resuelta" and inc["sola"] is True
PY
python3 "$P/hseo_crons.py" plan web | jq -e 'any(.[]; .nombre == "vigilancia" and .orden == ["vigilancia", "web"])' >/dev/null && ok "el plan de crons incluye la vigilancia" || bad "cron vigilancia"
exit $fail
