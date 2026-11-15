#!/usr/bin/env bash
# Parte semanal sin IA: cifras, faltas, lo hecho, puertas, hasta 3 propuestas validadas (una de título como mucho),
# «haz la N» lanza una vez; el cron del lunes existe.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
P="$ROOT/plugin/hermes-seo"; H="python3 $P/hseo_cli.py"
python3 "$P/hseo_clientes.py" alta web web.com --estado repo --nombre "La Web" >/dev/null
python3 "$P/hseo_clientes.py" config web capacidades.publicacion '{"adaptador":"repo-pr","repo":"/tmp/r"}' >/dev/null
python3 "$P/hseo_clientes.py" config web capacidades.busqueda '{"gsc":"sc-domain:web.com"}' >/dev/null 2>&1 || true
si "sin datos el parte sale igual y dice qué falta" "$H parte web --no-guardar | grep -q 'Falta: Search Console'"
python3 - "$HERMES_SEO_HOME/clientes/web" <<'PY'
import json, sys
from datetime import date, timedelta
from pathlib import Path
d = Path(sys.argv[1]) / "datos" / "gsc"; d.mkdir(parents=True)
hoy = date.today()
for i in range(56):
    f = hoy - timedelta(days=58 - i)
    datos = {"totales": {"clics": 3, "impresiones": 300, "ctr": 0.01, "posicion": 9.0},
             "consulta_pagina": [{"query": "que es x", "page": "https://web.com/x", "clics": 0, "impresiones": 30, "ctr": 0, "posicion": 12.0}],
             "pagina": [{"page": "https://web.com/a", "clics": 0, "impresiones": 60, "ctr": 0, "posicion": 5.0},
                        {"page": "https://web.com/b", "clics": 0, "impresiones": 40, "ctr": 0, "posicion": 6.0}]}
    (d / f"{f.isoformat()}.json").write_text(json.dumps(datos))
PY
python3 "$P/hseo_datos.py" actualizar web >/dev/null
OUT=$($H parte web)
echo "$OUT" | grep -q "📊 Parte de la semana · La Web" && echo "$OUT" | grep -q "84 clics" && ok "cifras de 28 días" || bad "cifras ($OUT)"
N=$(echo "$OUT" | grep -c '^[0-9]\. ')
[ "$N" -ge 1 ] && [ "$N" -le 3 ] && ok "entre 1 y 3 propuestas" || bad "propuestas ($N)"
[ "$(echo "$OUT" | grep -c 'Mejorar el título')" -le 1 ] && ok "como mucho una de título" || bad "una de título"
si "se guarda ultimo.json" "[ -f $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json ]"
si "haz la 1: lanza" "$H propuesta web 1 | grep -q '✅ Propuesta 1'"
si "haz la 1 otra vez: ya se lanzó" "$H propuesta web 1 | grep -q 'ya se lanzó'"
si "el siguiente parte ya no la propone (está en marcha)" "! $H parte web --no-guardar | grep -q \"\$(jq -r '.propuestas[0].texto' $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json | cut -c1-40)\""
si "una propuesta que no existe se rechaza" "! $H propuesta web 9"
si "el plan de crons incluye el parte del lunes a las 10:30" "python3 $P/hseo_crons.py plan web | jq -e 'any(.[]; .nombre == \"parte\" and .horario == \"30 10 * * 1\" and .orden == [\"parte\", \"web\"])'"
exit $fail
