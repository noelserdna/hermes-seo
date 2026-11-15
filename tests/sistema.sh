#!/usr/bin/env bash
# Salud del servidor: revisar repara (como mucho 3 al día) y deja sistema.json; avisos cuenta solo lo que no se arregló,
# una vez; avisa si la revisión o la vigilancia de una web dejan de correr.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HOME="$T/casa" FALSO_LLAMADAS="$T/llamadas"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com >/dev/null
python3 - "$P" <<'PY' && ok "disco lleno: repara (en seco), y si sigue avisa una vez con lo probado; olvida lo resuelto" || bad "disco"
import importlib.util, os, sys, time
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, S = m("hseo_base"), m("hseo_sistema")
os.environ["HSEO_AVISO_DISCO"] = "0"
r = S.revisar(seco=True)
assert r["reparaciones"] and r["reparaciones"][0]["que"] == "disco" and any(p["firma"].startswith("disco") for p in r["problemas"]), r
av = S.avisos(); assert any("disco" in a and "Ya probé" in a for a in av), av
assert S.avisos() == []                                         # no se repite
for _ in range(3): S.revisar(seco=True)
assert S._hoy_reparaciones(B.leer(B.home() / "sistema.json")) <= 3
os.environ["HSEO_AVISO_DISCO"] = "101"; S.revisar(seco=True); assert S.avisos() == []
B.escribir(B.home() / "sistema.json", {"ts": "2020-01-01T00:00:00Z", "problemas": []})
assert any("no corre" in a for a in S.avisos())
PY
python3 - "$P" <<'PY' && ok "vigilancia de una web parada: avisa" || bad "vigilancia parada"
import importlib.util, sys
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, C, S = m("hseo_base"), m("hseo_clientes"), m("hseo_sistema")
B.escribir(C.carpeta("web") / "vigilancia.json", {"ts": "2020-01-01T00:00:00Z"})
S.revisar(seco=True)
assert any("vigilancia de web" in a for a in S.avisos())
PY
exit $fail
