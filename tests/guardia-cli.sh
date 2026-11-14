#!/usr/bin/env bash
# El guardia (coordinadora y encargados): qué pueden hacer solos, qué pide aprobación y qué nunca. Y la CLI hseo.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
H="$ROOT/hseo"; G="$ROOT/encargado/guardia.py"; A="$ROOT"
$H alta web web.com >/dev/null; $H alta otra otra.com >/dev/null
mkdir -p "$HERMES_SEO_HOME/wiki"

# t <rc esperado> <ámbito> <evento> <nombre>   · aprueba <ámbito> <evento> <nombre> (rc 0 + {"action":"approve"})
t() { out=$(printf '%s' "$3" | python3 -I "$G" "$2" "$A" 2>/dev/null); rc=$?
      if [ "$rc" = "$1" ] && ! echo "$out" | grep -q '"approve"'; then ok "$4"; else bad "$4 (salió $rc: $out)"; fi; }
aprueba() { out=$(printf '%s' "$2" | python3 -I "$G" "$1" "$A" 2>/dev/null); rc=$?
      if [ "$rc" = 0 ] && echo "$out" | grep -q '"action": "approve"'; then ok "$3"; else bad "$3 (salió $rc: $out)"; fi; }
c() { jq -nc --arg c "$1" '{tool_name:"terminal",tool_input:{command:$c}}'; }
w() { jq -nc --arg t "$1" --arg p "$2" '{tool_name:$t,tool_input:{path:$p,content:"x"}}'; }
CL="$HERMES_SEO_HOME/clientes"

# ── la coordinadora (cartera) ──
t 0 cartera "$(c 'hseo estado')" "coordinadora: estado de todo"
t 0 cartera "$(c 'hseo lanzar web radar')" "coordinadora: lanzar una pipeline, sola"
t 0 cartera "$(c "bash $A/hseo encargos web")" "coordinadora: hseo por su ruta del arnés"
t 0 cartera "$(c 'hseo reintentar web radar-x-1a2b radar')" "coordinadora: reintentar, sola"
aprueba cartera "$(c 'hseo alta nueva nueva.com --estado wordpress')" "coordinadora: el alta pide aprobación"
aprueba cartera "$(c 'hseo config web competidores "[\"a.com\"]"')" "coordinadora: config pide aprobación"
aprueba cartera "$(c 'hseo jev modo auto web')" "coordinadora: cambiar el modo de Jev pide aprobación"
aprueba cartera "$(c 'hseo modelos perfil calidad')" "coordinadora: cambiar modelos pide aprobación"
aprueba cartera "$(c 'hseo pausar todo')" "coordinadora: pausar pide aprobación"
aprueba cartera "$(c 'hseo lanzar web articulo --param tema=x --excepcion')" "coordinadora: una excepción pide aprobación"
aprueba cartera "$(c 'hseo lanzar web visibilidad-ia')" "coordinadora: una pipeline con coste externo pide aprobación"
t 0 cartera "$(c 'hseo jev ver')" "coordinadora: ver Jev, sola"
t 2 cartera "$(c 'hseo decidir g123 acepto')" "nunca: decidir una puerta (no existe)"
t 2 cartera "$(c "python3 $A/plugin/hermes-seo/hseo_puertas.py decidir-local g1 acepto")" "nunca: llamar al notario directamente"
t 2 cartera "$(c "bash $A/etapa.sh web x y")" "nunca: ejecutar etapas a mano"
t 2 cartera "$(c "cat $CL/web/secretos.env")" "nunca: leer secretos"
t 2 cartera "$(c "cat $HERMES_SEO_HOME/aprobadores.json")" "nunca: leer aprobadores"
t 2 cartera "$(c 'cat ~/.hermes/.env')" "nunca: leer el .env de Hermes"
t 2 cartera "$(c 'cat ~/.hermes/config.yaml')" "nunca: leer el resto de Hermes"
t 2 cartera "$(c 'echo x > /tmp/a')" "nunca: redirigir a un fichero"
t 2 cartera "$(c 'cat $(echo x)')" "nunca: sustituciones"
t 2 cartera "$(c 'rm -rf /tmp/a')" "nunca: rm"
t 2 cartera "$(c 'curl -X POST https://a.com -d x')" "nunca: enviar datos con curl"
t 0 cartera "$(c 'curl -sI https://web.com/')" "coordinadora: mirar las cabeceras de una web"
t 0 cartera "$(c "cat $CL/web/encargos.jsonl 2>/dev/null | tail -5")" "coordinadora: leer datos del cliente"
t 2 cartera "$(jq -nc '{tool_name:"execute_code",tool_input:{code:"1"}}')" "nunca: execute_code"
t 0 cartera "$(w write_file "$HERMES_SEO_HOME/wiki/conceptos/x.md")" "coordinadora: escribe en la wiki global"
t 0 cartera "$(w write_file "$CL/web/briefs/b.md")" "coordinadora: escribe un brief"
t 2 cartera "$(w write_file "$CL/web/cliente.json")" "nunca: escribir la configuración a mano"
t 2 cartera "$(w patch "$CL/web/wiki/.git/config")" "nunca: tocar el .git del wiki"
t 0 cartera "$(c "git -C $HERMES_SEO_HOME/wiki commit -am x")" "coordinadora: commit en la wiki global"
t 2 cartera "$(c "git -C $HERMES_SEO_HOME/wiki push")" "nunca: push de la wiki"

# ── el encargado de una web ──
t 0 web "$(c 'hseo estado web')" "encargado: estado de su web"
t 0 web "$(c 'hseo lanzar web articulo --param tema=x')" "encargado: lanzar en su web"
t 2 web "$(c 'hseo lanzar otra radar')" "encargado: no lanza en otra web"
t 2 web "$(c 'hseo estado')" "encargado: no ve el estado de todas"
t 2 web "$(c 'hseo alta nueva nueva.com')" "encargado: no da de alta webs"
aprueba web "$(c 'hseo config web negocio.publico "Pymes"')" "encargado: config de su web con aprobación"
t 2 web "$(c 'hseo config otra negocio.publico x')" "encargado: no configura otra web"
t 2 web "$(c 'hseo pausar todo')" "encargado: no pausa todo"
t 2 web "$(c 'hseo modelos perfil rapido')" "encargado: no cambia los modelos globales"
aprueba web "$(c 'hseo modelos poner redactar sonnet --cliente web')" "encargado: modelos de su web con aprobación"
t 0 web "$(c 'hseo modelos ver')" "encargado: ver modelos"
t 2 web "$(c "cat $CL/otra/encargos.jsonl")" "encargado: no lee otra web"
t 0 web "$(w write_file "$CL/web/wiki/entities/x.md")" "encargado: escribe en su wiki"
t 2 web "$(w write_file "$CL/otra/wiki/x.md")" "encargado: no escribe en la wiki de otra web"
t 2 web "$(w write_file "$HERMES_SEO_HOME/wiki/x.md")" "encargado: la wiki global solo por lecciones"
t 2 web "$(jq -nc --arg p "$CL/otra/brief.md" '{tool_name:"read_file",tool_input:{path:$p}}')" "encargado: read_file de otra web"

# ── la CLI ──
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }
si "hseo clientes" "$H clientes | grep -q web.com"
si "hseo plan dice el modelo" "$H plan estrategia web | grep -q 'opus\|sonnet'"
EID=$($H lanzar web radar | sed -nE 's/.*\((radar-[a-z0-9-]+)\).*/\1/p')
si "hseo lanzar devuelve el encargo" "[ -n '$EID' ]"
si "hseo estado lo enseña" "$H estado web | grep -q '$EID'"
si "reintentar una vez" "$H reintentar web $EID radar"
no "reintentar dos veces, no" "$H reintentar web $EID radar"
si "pausar y reanudar una web" "$H pausar web && $H estado web | grep -q 'en pausa' && $H reanudar web"
si "jev modo por web" "$H jev modo consejo web && $H jev ver | grep -q '\"web\": \"consejo\"'"
no "hseo no tiene orden para decidir" "$H decidir x acepto"
exit $fail
