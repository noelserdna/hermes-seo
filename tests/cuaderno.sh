#!/usr/bin/env bash
# Cuaderno del método: cifras de la semana sin modelo (etapas, cambios de la verificación, puertas, incidencias, coste
# por perfil desde state.db en solo lectura), en la wiki global, sin textos de las webs.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HOME="$T/casa" HERMES_HOME_BASE="$T/hh"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com >/dev/null
python3 - "$HERMES_SEO_HOME/clientes/web" "$T/hh" <<'PY'
import json, sqlite3, sys, time
from pathlib import Path
W, HH = Path(sys.argv[1]), Path(sys.argv[2])
ahora = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
with open(W / "etapas.jsonl", "w") as f:
    for r in [("articulo", "verificar", "cambios"), ("articulo", "verificar", "done"), ("articulo", "redactar", "failed"), ("articulo", "redactar", "done")]:
        f.write(json.dumps({"ts": ahora, "pipeline": r[0], "etapa": r[1], "resultado": r[2], "minutos": 3, "coste_usd": 0.5}) + "\n")
(W / "puertas.jsonl").write_text(json.dumps({"ts": ahora, "tipo": "publicar", "verbo": "cambios", "texto": "SECRETO DE LA WEB", "segundos_hasta_decidir": 7200}) + "\n")
(HH / "profiles" / "seo-estacion").mkdir(parents=True)
con = sqlite3.connect(HH / "profiles" / "seo-estacion" / "state.db")
con.execute("CREATE TABLE sessions (source TEXT, started_at REAL, estimated_cost_usd REAL)")
con.execute("INSERT INTO sessions VALUES ('kanban', ?, 1.25)", (time.time(),)); con.commit()
PY
python3 "$ROOT/plugin/hermes-seo/hseo_cli.py" cuaderno apuntar >/dev/null && ok "apunta la semana" || bad "apuntar"
F=$(ls $HERMES_SEO_HOME/wiki/queries/semana-*.md 2>/dev/null | head -1)
[ -n "$F" ] && grep -q "articulo/redactar | 2 | 50 %" "$F" && grep -q "pidió cambios: 50 %" "$F" && grep -q "seo-estacion: kanban 1 ses. 1.25" "$F" && ok "fallos por etapa, cambios de la verificación y coste por perfil" || bad "cifras ($(cat "$F" 2>/dev/null | head -20))"
! grep -q "SECRETO DE LA WEB" "$F" $HERMES_SEO_HOME/wiki/queries/*.json && ok "sin textos de las webs" || bad "se coló texto de una web"
grep -q "\[\[metodo-cifras\]\]" $HERMES_SEO_HOME/wiki/index.md && [ -f $HERMES_SEO_HOME/wiki/concepts/metodo-cifras.md ] && ok "tabla de 12 semanas en la wiki global" || bad "metodo-cifras"
exit $fail
