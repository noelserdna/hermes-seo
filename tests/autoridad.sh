#!/usr/bin/env bash
# Autoridad y presencia: citas por código (dónde salen otros y no la web), la puerta con «Todas / Solo algunas / No»,
# las del sistema se lanzan, las de la persona salen en el parte hasta marcarlas hechas.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros" HERMES_SEO_DESHACER_S=0
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
P="$ROOT/plugin/hermes-seo"; H="python3 $P/hseo_cli.py"
python3 "$P/hseo_clientes.py" alta web web.com --estado repo >/dev/null
python3 "$P/hseo_clientes.py" config web capacidades.publicacion '{"adaptador":"repo-pr","repo":"/tmp/r"}' >/dev/null
echo "{\"ana\":{\"nombre\":\"Ana\",\"canales\":{\"telegram\":\"111\",\"local\":\"$(id -un)\"},\"clientes\":[\"*\"]}}" > "$HERMES_SEO_HOME/aprobadores.json"
mkdir -p $HERMES_SEO_HOME/clientes/web/datos/ia
cat > $HERMES_SEO_HOME/clientes/web/datos/ia/decision-2026-11-01-claude.json <<'J'
{"filas": [{"pregunta": "mejor curso", "citas": ["https://glama.ai/x", "https://www.udemy.com/c", "https://blog.ejemplo.es/top"]},
           {"pregunta": "otra", "citas": ["https://glama.ai/y", "https://reddit.com/r/z"]},
           {"pregunta": "nos cita", "citas": ["https://web.com/a", "https://glama.ai/z"]}]}
J
R=$(python3 "$P/hseo_autoridad.py" citas web)
echo "$R" | jq -e '.sin_la_web == 2 and .fuentes[0].dominio == "glama.ai" and .fuentes[0].veces == 2 and .fuentes[0].clase == "lista-o-directorio"' >/dev/null && ok "citas: solo donde la web no sale, contadas y clasificadas" || bad "citas ($R)"
echo "$R" | jq -e '([.accionables[].dominio] | index("udemy.com")) == null' >/dev/null && ok "las plataformas de cursos no son accionables" || bad "accionables"
EID=$(python3 "$P/hseo_encargos.py" lanzar web autoridad | jq -r .encargo)
D=$HERMES_SEO_HOME/clientes/web/encargos/$EID
OUT=$(FALSO_MODO=ok bash "$ROOT/etapa.sh" web "$EID" gestiones | tail -1)
si "la etapa recibe datos-citas.json (prepara)" "[ -f $D/datos-citas.json ]"
cat > $D/gestiones.json <<'J'
{"gestiones": [{"n": 1, "destino": "glama.ai", "tipo": "ficha-directorio", "quien": "persona", "texto": "Alta del servidor"},
               {"n": 2, "destino": "Página de respuesta", "tipo": "pieza-propia", "quien": "sistema", "texto": "Página que responde «mejor curso»"},
               {"n": 3, "destino": "reddit", "tipo": "respuesta-foro", "quien": "persona", "texto": "Respuesta útil"}]}
J
G=$(echo "$OUT" | jq -r '.puerta // empty')
si "abre la puerta con «Todas / Solo algunas / No»" "[ -n '$G' ] && python3 $P/hseo_puertas.py ver $G | jq -e '[.opciones[].verbo] == [\"acepto\",\"algunas\",\"rechazo\"]'"
si "«Solo algunas: 1,2»: lanza la del sistema y apunta la tuya" "python3 $P/hseo_puertas.py decidir-local $G algunas '1,2' | grep -q 'lanzadas cambio-seo-' && [ \$(grep -c '\"quien\": \"persona\"' $HERMES_SEO_HOME/clientes/web/gestiones.jsonl) = 1 ]"
si "la gestión tuya sale en el parte" "$H parte web --no-guardar | grep -q 'Tu parte (autoridad.*1. glama.ai'"
si "marcarla hecha la quita" "$H gestion hecha web 1 https://glama.ai/web && ! $H parte web --no-guardar | grep -q 'Tu parte'"
exit $fail
