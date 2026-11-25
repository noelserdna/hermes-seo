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
             "pagina": [{"page": "https://web.com/x", "clics": clics, "impresiones": 400, "ctr": 0.03, "posicion": 11.0},
                        {"page": "https://web.com/sin-clics", "clics": 0, "impresiones": 100, "ctr": 0, "posicion": 3.0},
                        {"page": "https://web.com/poco", "clics": 0, "impresiones": 2, "ctr": 0, "posicion": 1.0}],
             "pais": [{"country": "esp", "clics": 15, "impresiones": 600, "ctr": 0.025, "posicion": 10.0},
                      {"country": "mex", "clics": 5, "impresiones": 400, "ctr": 0.0125, "posicion": 20.0}],
             "dispositivo": [{"device": "DESKTOP", "clics": 18, "impresiones": 800, "ctr": 0.02, "posicion": 12.0}]}
    (d / f"{f.isoformat()}.json").write_text(json.dumps(datos))
(Path(sys.argv[1]) / "cambios.jsonl").write_text(json.dumps({"id": "c-art-x", "ts": "2026-09-14T10:00:00Z",
    "encargo": "art-x", "url": "https://web.com/x/", "hipotesis": "más clics"}) + "\n")
PY
si "actualizar carga 100 días" "python3 $ROOT/plugin/hermes-seo/hseo_datos.py actualizar web | grep -q '^100 días'"
si "es idempotente" "python3 $ROOT/plugin/hermes-seo/hseo_datos.py actualizar web | grep -q '^100 días' && [ \$(python3 -c \"import sqlite3,sys;print(sqlite3.connect(sys.argv[1]).execute('select count(*) from gsc_dia').fetchone()[0])\" $HERMES_SEO_HOME/clientes/web/datos/metricas.db) = 100 ]"
R=$($H datos resumen web)
echo "$R" | jq -e '.actual.clics == 700 and .anterior.clics == 690 and .actual.dias == 28' >/dev/null && ok "resumen: 28 días frente a los 28 anteriores" || bad "resumen ($(echo "$R" | jq -c '.actual,.anterior'))"
echo "$R" | jq -e '[.pagina_dos[].consulta] == ["qué es x"]' >/dev/null && ok "resumen: consultas en posiciones 8-20 (no la de la posición 4)" || bad "página 2"
echo "$R" | jq -e '(.serie | length) == 90' >/dev/null && ok "resumen: serie de 90 días para el panel" || bad "serie"
echo "$R" | jq -e '.paises[0].pais == "esp" and .paises[0].impresiones == 16800 and .paises[1].posicion == 20' >/dev/null && ok "resumen: países (antes no se cargaban)" || bad "países ($(echo "$R" | jq -c '.paises'))"
echo "$R" | jq -e '.dispositivos[0].dispositivo == "DESKTOP"' >/dev/null && ok "resumen: dispositivos" || bad "dispositivos"
echo "$R" | jq -e '[.bajo_ctr[].pagina] == ["https://web.com/sin-clics"]' >/dev/null && ok "bajo_ctr: muchas impresiones y pocos clics para su posición (no las de pocas impresiones)" || bad "bajo_ctr ($(echo "$R" | jq -c '.bajo_ctr'))"
echo "$R" | jq -e '.marca.terminos == ["web"] and .curva_ctr == "propia"' >/dev/null && ok "marca por el dominio; con más de 500 clics, curva propia" || bad "marca/curva"
python3 - "$HERMES_SEO_HOME/clientes/web/datos/metricas.db" <<'PY' && ok "posición ponderada por impresiones (no la media de días)" || bad "posición ponderada"
import sqlite3, sys, importlib.util
con = sqlite3.connect(sys.argv[1])
p = con.execute("SELECT SUM(posicion*impresiones)/SUM(impresiones) FROM gsc_pais").fetchone()[0]
assert abs(p - 14.0) < 0.01, p
PY
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
python3 - "$ROOT/plugin/hermes-seo" "$HERMES_SEO_HOME/clientes/web" <<'PY' && ok "prepara: el código deja datos-resumen.json antes de la etapa" || bad "prepara"
import importlib.util, json, sys
from pathlib import Path
P, W = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("hseo_etapa", P / "hseo_etapa.py")
m = importlib.util.module_from_spec(spec); sys.modules["hseo_etapa"] = m; spec.loader.exec_module(m)
d = W / "encargos" / "prueba-prepara"; d.mkdir(parents=True, exist_ok=True)
m.preparar("web", d, "resumen")
r = json.loads((d / "datos-resumen.json").read_text())
assert r["hay_datos"] and r["paises"] and "bajo_ctr" in r
PL = sys.modules["hseo_pipelines"]
assert not PL.validar(PL.cargar("metricas-semanales")) and PL.validar({"id": "x", "nombre": "x", "etapas": [{"id": "a", "perfil": "seo-analista", "skill": "metricas", "prepara": ["inventado"]}]})
PY
python3 - "$ROOT/plugin/hermes-seo" "$HERMES_SEO_HOME/clientes/web" <<'PY' && ok "ia: cita y mención por motor con intervalo; «sube» solo si los intervalos no se solapan" || bad "ia"
import importlib.util, json, sys
from pathlib import Path
P, W = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_ia", P / "hseo_ia.py"); IA = importlib.util.module_from_spec(s); sys.modules["hseo_ia"] = IA; s.loader.exec_module(IA)
d = W / "datos" / "ia"; d.mkdir(parents=True, exist_ok=True)
fila = lambda c: {"respuesta": "texto", "citas": ["https://web.com/a"] if c else ["https://otro.com"]}
(d / "chatgpt-2026-10-01.json").write_text(json.dumps({"filas": [fila(False)] * 30}))
(d / "chatgpt-2026-11-01.json").write_text(json.dumps({"filas": [fila(True)] * 20 + [fila(False)] * 10 + [{"error": "x"}]}))
r = IA.guardar("web")
m = r["motores"]["chatgpt"]
assert r["fecha"] == "2026-11-01" and m["respuestas"] == 30 and m["cita"] == 20 and m["intervalo_cita"][0] > 0.4, r
assert r["cambios"]["chatgpt"] == "sube" and (d / "resumen-2026-11-01.json").exists()
(d / "chatgpt-2026-11-15.json").write_text(json.dumps({"filas": [{"error": "HTTP Error 429"}] * 30}))
r = IA.resumen("web", "2026-11-15")
assert r["motores"]["chatgpt"]["sin_datos"] and "chatgpt" not in r["cambios"], r   # una ronda fallida no es una bajada
# el mismo motor con el modelo de la versión gratuita, en la misma ronda: se cuenta aparte y se compara con el principal
(d / "chatgpt-2026-12-01.json").write_text(json.dumps({"modelo": "gpt-5.5", "filas": [fila(True)] * 20 + [fila(False)] * 10}))
(d / "chatgpt-gpt-5.6-luna-2026-12-01.json").write_text(json.dumps({"modelo": "gpt-5.6-luna", "filas": [fila(True)] * 2 + [fila(False)] * 28}))
r = IA.resumen("web", "2026-12-01")
g = r["motores"]["chatgpt · gpt-5.6-luna"]
assert g["modelo"] == "gpt-5.6-luna" and g["cita"] == 2 and r["motores"]["chatgpt"]["cita"] == 20, r
assert r["modelos"]["chatgpt · gpt-5.6-luna"]["diferencia"] == "menos citas" and r["modelos"]["chatgpt · gpt-5.6-luna"]["frente_a"] == "gpt-5.5", r
PY
exit $fail
