#!/usr/bin/env bash
# Aterrizaje de una web nueva: pasos que se comprueban solos, ningún cron con acceso sin comprobar, los mínimos lanzan
# la línea base UNA vez, omitir solo 6-8, las webs que ya existían (sin aterrizaje) no cambian, claves solo por terminal.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros" HSEO_SIN_RED=1
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }
P="$ROOT/plugin/hermes-seo"; H="python3 $P/hseo_cli.py"; CL="python3 $P/hseo_clientes.py"
$CL alta vieja vieja.com >/dev/null; $CL alta nueva nueva.com --estado repo >/dev/null
echo '{"yo":{"nombre":"Yo","canales":{"local":"x"},"clientes":["*"]}}' > "$HERMES_SEO_HOME/aprobadores.json"
si "una web sin aterrizaje (legado) conserva sus crons" "python3 $P/hseo_crons.py plan vieja | jq -e 'any(.[]; .nombre == \"datos\") and any(.[]; .nombre == \"parte\")'"
$H aterrizaje empezar nueva >/dev/null
si "web nueva: la lista dice «n de 10» y el siguiente paso" "$H aterrizaje ver nueva | grep -q '🛬 Aterrizaje de .* de 10' && $H aterrizaje ver nueva | grep -q 'Siguiente: Qué es la web'"
si "sin Search Console comprobado no hay cron de datos; sin negocio, no hay parte; la vigilancia sí" "python3 $P/hseo_crons.py plan nueva | jq -e '(any(.[]; .nombre == \"datos\") | not) and (any(.[]; .nombre == \"parte\") | not) and any(.[]; .nombre == \"vigilancia\")'"
no "un paso no se marca porque sí: omitir el 5 no vale" "$H aterrizaje omitir nueva 5"
si "omitir el 6 (Bing) sí" "$H aterrizaje omitir nueva 6 | grep -q '➖ 6.'"
mkdir -p "$T/repo/.git" "$HERMES_SEO_HOME/clientes/nueva/datos/gsc"; echo '{}' > "$HERMES_SEO_HOME/clientes/nueva/datos/gsc/2026-11-01.json"
$CL config nueva negocio '{"publico":"pymes","objetivo":"100 clics","conversion":"alta"}' >/dev/null
$CL config nueva capacidades.publicacion "{\"adaptador\":\"repo-pr\",\"repo\":\"$T/repo\"}" >/dev/null
$CL config nueva capacidades.busqueda '{"gsc":"sc-domain:nueva.com"}' >/dev/null
$H aterrizaje comprobar nueva >/dev/null
si "con la plantilla sin confirmar, el paso 2 (idiomas) no cuenta y no hay línea base" "jq -e '(.pasos[\"2\"].ok | not) and (.lanzados[\"linea-base\"] == null)' $HERMES_SEO_HOME/clientes/nueva/aterrizaje.json"
$CL config nueva mercados '[{"pais":"ES","bing":"es-ES"}]' >/dev/null
$H aterrizaje comprobar nueva >/dev/null
si "con los mínimos (1, 2, 3, 5) se lanza la línea base" "jq -e '.lanzados[\"linea-base\"] | startswith(\"linea-base-\")' $HERMES_SEO_HOME/clientes/nueva/aterrizaje.json"
$H aterrizaje comprobar nueva >/dev/null
si "y solo una vez" "[ \$(ls $HERMES_SEO_HOME/clientes/nueva/encargos | grep -c '^linea-base-') = 1 ]"
si "con Search Console comprobado ya hay cron de datos" "python3 $P/hseo_crons.py plan nueva | jq -e 'any(.[]; .nombre == \"datos\") and any(.[]; .nombre == \"parte\")'"
si "las claves no se guardan si no es desde una terminal" "! echo valor | $H secreto guardar nueva BING_API_KEY 2>&1 | grep -q guardada"
exit $fail
