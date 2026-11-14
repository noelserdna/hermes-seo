#!/usr/bin/env bash
# Telemetría: cargar las fotos de Search Console en metricas.db, resumen 28 frente a 28, «página 2», comparar un cambio.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
H="$ROOT/hseo"
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
$H alta web web.com >/dev/null
python3 - "$HERMES_SEO_HOME/clientes/web" <<'PY'
import json, sys
from datetime import date, timedelta
from pathlib import Path
d = Path(sys.argv[1]) / "datos" / "gsc"; d.mkdir(parents=True)
inicio = date(2026, 8, 1)
for i in range(100):
    f = inicio + timedelta(days=i)
    despues = f >= date(2026, 9, 15)
    clics = 20 if despues else 10
    datos = {"totales": {"clics": clics + 5, "impresiones": 1000, "ctr": 0.02, "posicion": 12.0},
             "consulta_pagina": [{"query": "qué es x", "page": "https://web.com/x", "clics": clics, "impresiones": 400, "ctr": 0.03, "posicion": 11.0},
                                 {"query": "x precio", "page": "https://web.com/precio", "clics": 5, "impresiones": 100, "ctr": 0.05, "posicion": 4.0}],
             "pagina": [{"page": "https://web.com/x", "clics": clics, "impresiones": 400, "ctr": 0.03, "posicion": 11.0}]}
    (d / f"{f.isoformat()}.json").write_text(json.dumps(datos))
(Path(sys.argv[1]) / "cambios.jsonl").write_text(json.dumps({"id": "c-art-x", "ts": "2026-09-14T10:00:00Z",
    "encargo": "art-x", "url": "https://web.com/x/", "hipotesis": "más clics"}) + "\n")
PY
si "actualizar carga 100 días" "python3 $ROOT/plugin/hermes-seo/hseo_datos.py actualizar web | grep -q '^100 días'"
si "es idempotente" "python3 $ROOT/plugin/hermes-seo/hseo_datos.py actualizar web | grep -q '^100 días' && [ \$(sqlite3 $HERMES_SEO_HOME/clientes/web/datos/metricas.db 'select count(*) from gsc_dia') = 100 ]"
R=$($H datos resumen web)
echo "$R" | jq -e '.actual.clics == 700 and .anterior.clics == 690 and .actual.dias == 28' >/dev/null && ok "resumen: 28 días frente a los 28 anteriores" || bad "resumen ($(echo "$R" | jq -c '.actual,.anterior'))"
echo "$R" | jq -e '[.pagina_dos[].consulta] == ["qué es x"]' >/dev/null && ok "resumen: consultas en posiciones 8-20 (no la de la posición 4)" || bad "página 2"
echo "$R" | jq -e '(.serie | length) == 90' >/dev/null && ok "resumen: serie de 90 días para el panel" || bad "serie"
R=$($H datos comparar web c-art-x)
echo "$R" | jq -e '.listo and .urls["https://web.com/x/"].antes.clics == 280 and .urls["https://web.com/x/"].despues.clics == 560' >/dev/null && ok "comparar: la URL del cambio antes y después (sin depender de la barra final)" || bad "comparar ($(echo "$R" | jq -c '.urls'))"
echo "$R" | jq -e '.web.antes.clics < .web.despues.clics' >/dev/null && ok "comparar: y la web entera para descontar la tendencia" || bad "comparar web"
python3 - "$HERMES_SEO_HOME/clientes/web" <<'PY'
import json, sys
from pathlib import Path
with open(Path(sys.argv[1]) / "cambios.jsonl", "a") as f:
    f.write(json.dumps({"id": "c-reciente", "ts": "2026-10-30T10:00:00Z", "url": "https://web.com/x"}) + "\n")
PY
$H datos comparar web c-reciente | jq -e '.listo == false and (.motivo | test("28 días"))' >/dev/null && ok "comparar: sin 28 días después, lo dice" || bad "comparar reciente"
$H datos comparar web no-existe >/dev/null 2>&1 && bad "comparar un cambio inventado" || ok "comparar: un cambio que no existe da error"
si "recoger sin capacidades: no falla ni avisa" "[ -z \"\$($H datos recoger web)\" ]"
exit $fail
