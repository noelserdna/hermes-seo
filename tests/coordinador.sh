#!/usr/bin/env bash
# La coordinadora habla con el encargado de una web (preguntar/ordenar): sesión «coordinador» continua del perfil
# seo-p-<web>, respuesta limpia, registro en acciones.jsonl; un encargado no puede.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HOME="$T/casa" FALSO_LLAMADAS="$T/llamadas"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
P="$ROOT/plugin/hermes-seo"; H="python3 $P/hseo_cli.py"
mkdir -p "$T/bin"; cat > "$T/bin/hermes" <<'SH'
#!/usr/bin/env bash
echo "$*" >> "$FALSO_LLAMADAS"; echo "Hay 1 puerta abierta desde el 14-11."; echo "session_id: abc"
SH
chmod +x "$T/bin/hermes"; export HERMES_BIN="$T/bin/hermes"
python3 "$P/hseo_clientes.py" alta web web.com >/dev/null
OUT=$($H preguntar web "¿qué tienes pendiente?")
[ "$OUT" = "Hay 1 puerta abierta desde el 14-11." ] && ok "preguntar devuelve la respuesta limpia (sin la línea de sesión)" || bad "preguntar ($OUT)"
si "con el perfil del encargado y la sesión «coordinador» continua" "grep -q -- '-p seo-p-web chat -Q -q' $FALSO_LLAMADAS && grep -q -- '-c coordinador --create-if-missing' $FALSO_LLAMADAS"
si "queda apuntado en acciones.jsonl (web y global)" "jq -e '.tipo == \"preguntar\" and .web == \"web\"' $HERMES_SEO_HOME/clientes/web/acciones.jsonl && [ -s $HERMES_SEO_HOME/acciones.jsonl ]"
si "ordenar lleva el prefijo de orden" "$H ordenar web 'lanza el radar' && grep -q 'Orden del coordinador' $FALSO_LLAMADAS"
si "desde el perfil de un encargado, no" "! HSEO_AMBITO=seo-p-web $H preguntar web hola"
si "una web que no existe, no" "! $H preguntar otra hola"
exit $fail
