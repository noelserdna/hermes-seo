#!/usr/bin/env bash
# Tandas: candidatas por código (impresiones, días, estabilidad, posición, pocos clics), control parecido, límites,
# lanzar en un solo encargo (una vez), las páginas de una tanda no se tocan por otro lado, y el veredicto sin modelo.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros" HSEO_SIN_RED=1
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com --estado repo >/dev/null
python3 "$P/hseo_clientes.py" config web capacidades.publicacion '{"adaptador":"repo-pr","repo":"/tmp/r"}' >/dev/null
python3 - "$HERMES_SEO_HOME/clientes/web" <<'PY'
import json, sys
from datetime import date, timedelta
from pathlib import Path
d = Path(sys.argv[1]) / "datos" / "gsc"; d.mkdir(parents=True)
hoy = date.today()
pags = {"a": (60, 6.0, 0), "b": (40, 7.0, 0), "c": (30, 9.0, 0), "d": (20, 5.5, 1), "e": (20, 6.5, 1), "f": (20, 7.5, 1),
        "home": (200, 3.0, 0), "poca": (2, 6.0, 0)}
for i in range(40):
    f = hoy - timedelta(days=42 - i)
    filas = [{"page": "https://web.com/" + ("" if k == "home" else k), "clics": c, "impresiones": imp, "ctr": 0, "posicion": pos}
             for k, (imp, pos, c) in pags.items()]
    (d / f"{f.isoformat()}.json").write_text(json.dumps({"totales": {"clics": 5, "impresiones": 400, "ctr": 0.01, "posicion": 7},
                                                         "consulta_pagina": [], "pagina": filas}))
PY
python3 "$P/hseo_datos.py" actualizar web >/dev/null
H="python3 $P/hseo_cli.py"
R=$($H tanda proponer web)
echo "$R" | jq -e '[.tratadas[].url] == ["https://web.com/a","https://web.com/b","https://web.com/c"]' >/dev/null && ok "candidatas: las de más clics perdidos, sin la portada ni las de pocas impresiones" || bad "candidatas ($(echo "$R" | jq -c '[.tratadas[].url]'))"
echo "$R" | jq -e '(.control | length) >= 2 and ([.control[].url] | index("https://web.com/a") | not)' >/dev/null && ok "control: parecidas y distintas de las tratadas" || bad "control"
$H tanda crear web >/dev/null && ok "crear T1" || bad "crear"
TJ=$HERMES_SEO_HOME/clientes/web/tandas/T1.json
jq -e '.estado == "abierta" and .ventana_dias == 28 and (.paginas | length) == 3 and .paginas[0].linea_base.impresiones > 0' $TJ >/dev/null && ok "la tanda guarda línea base, ventana y estado" || bad "T1.json"
$H tanda lanzar web T1 | grep -q "encargo" && jq -e '.encargo | startswith("cambio-seo-")' $TJ >/dev/null && ok "lanzar: un solo encargo cambio-seo, apuntado en la tanda" || bad "lanzar"
$H tanda lanzar web T1 | grep -q "ya estaba" && ok "lanzar otra vez no duplica" || bad "lanzar dos veces"
python3 "$P/hseo_encargos.py" lanzar web actualizacion --param url=https://web.com/d --param motivo=x >/dev/null 2>&1 && bad "una página de control se tocó por otro lado" || ok "una página de la tanda (control) no se toca por otro lado"
python3 - "$P" <<'PY' && ok "límites: una página no va en dos tandas; más de 4 no" || bad "límites"
import importlib.util, sys
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_tandas", P / "hseo_tandas.py"); T = importlib.util.module_from_spec(s); sys.modules["hseo_tandas"] = T; s.loader.exec_module(T)
def rechaza(f):
    try: f(); return False
    except T.Rechazo: return True
assert rechaza(lambda: T.limites("web", ["https://web.com/a"]))
assert rechaza(lambda: T.limites("web", [f"https://web.com/x{i}" for i in range(5)]))
PY
python3 - "$P" "$HERMES_SEO_HOME/clientes/web" <<'PY' && ok "veredicto: sin publicar, espera; con pocos datos, «no se puede saber»; cierra la tanda" || bad "veredicto"
import importlib.util, json, sys
from datetime import date, timedelta
from pathlib import Path
P, W = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_tandas", P / "hseo_tandas.py"); T = importlib.util.module_from_spec(s); sys.modules["hseo_tandas"] = T; s.loader.exec_module(T)
assert not T.veredicto("web", "T1")["listo"]
t = T.leer("web", "T1")
ts = (date.today() - timedelta(days=36)).isoformat() + "T10:00:00Z"
(W / "cambios.jsonl").write_text(json.dumps({"id": "c-x", "ts": ts, "encargo": t["encargo"]}) + "\n")
r = T.veredicto("web", "T1")
assert r["listo"] and r["salida"] == "no-se-puede-saber", r
assert T.leer("web", "T1")["estado"] == "cerrada" and (W / "tandas/T1-veredicto.json").exists()
PY
exit $fail
