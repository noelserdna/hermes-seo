#!/usr/bin/env bash
# Instalación (en un HOME de pruebas, con Hermes falso) y el encargado: perfil, carta, guardia, wiki, vigilancia y tema.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HOME="$T/casa" HERMES_BIN="$ROOT/tests/dobles/hermes" FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
unset HERMES_SEO_HOME
mkdir -p "$HOME/.hermes/hermes-agent/optional-skills/research/llm-wiki"
echo "# llm-wiki" > "$HOME/.hermes/hermes-agent/optional-skills/research/llm-wiki/SKILL.md"
printf 'TELEGRAM_BOT_TOKEN=secreto\nTELEGRAM_ALLOWED_USERS=12345\nCLAUDE_CODE_OAUTH_TOKEN=tok\n' > "$HOME/.hermes/.env"
echo "Eres mi asistente." > "$HOME/.hermes/SOUL.md"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
H="$HOME/.hermes"; S="$H/hermes-seo"

si "instalar sin la coordinadora" "bash $ROOT/instalar.sh"
si "copia versionada y enlace actual" "[ -L $S/actual ] && [ -f $S/actual/pipelines/articulo.json ] && [ ! -d $S/actual/tests ]"
si "la carpeta lleva versión y commit, e instalacion.json la apunta" "jq -e '.carpeta | test(\"/[0-9]+\\\\.[0-9]+\\\\.[0-9]+-\")' $S/instalacion.json"
si "llm-wiki copiada para los encargados" "[ -f $S/actual/encargado/skills/llm-wiki/SKILL.md ]"
si "aprobadores con el id de Telegram" "jq -e '.yo.canales.telegram == \"12345\"' $S/aprobadores.json"
si "plugin copiado y activado" "[ -f $H/plugins/hermes-seo/__init__.py ] && grep -q 'plugins enable hermes-seo' $FALSO_LLAMADAS"
si "la CLI hseo en ~/.local/bin" "[ -L $HOME/.local/bin/hseo ] && $HOME/.local/bin/hseo clientes"
si "perfiles creados: estación y 5 de rol" "[ \$(grep -c '^profile create' $FALSO_LLAMADAS) = 6 ]"
si "carta de rol = rol + reglas comunes" "grep -q 'Analista SEO' $H/profiles/seo-analista/SOUL.md && grep -q 'Reglas comunes' $H/profiles/seo-analista/SOUL.md"
si "los perfiles no reciben el token del bot" "! grep -q TELEGRAM $H/profiles/seo-analista/.env && grep -q CLAUDE_CODE_OAUTH_TOKEN $H/profiles/seo-analista/.env"
si "skills del arnés en los perfiles de rol" "grep -q 'seo-redactor config set skills.external_dirs' $FALSO_LLAMADAS"
si "sin --coordinadora no toca el SOUL principal" "[ \"\$(cat $H/SOUL.md)\" = 'Eres mi asistente.' ]"
echo "secreto viejo" > "$H/profiles/seo-analista/.env"
si "reinstalar no recrea perfiles ni pisa sus claves" "bash $ROOT/instalar.sh && [ \$(grep -c '^profile create' $FALSO_LLAMADAS) = 6 ] && grep -q 'secreto viejo' $H/profiles/seo-analista/.env"
si "con --coordinadora: carta y prohibiciones duras, sin guardia" "bash $ROOT/instalar.sh --coordinadora && grep -q 'Eres mi asistente' $H/SOUL.md && grep -q 'hermes-seo:inicio' $H/SOUL.md && grep -q 'config set approvals.deny .*hseo_puertas.py' $FALSO_LLAMADAS && [ ! -f $H/shell-hooks-allowlist.json ]"
si "con --coordinadora-estricta: además el guardia" "bash $ROOT/instalar.sh --coordinadora-estricta && grep -q 'guardia.py cartera' $H/shell-hooks-allowlist.json"
si "la carta no se duplica al reinstalar" "bash $ROOT/instalar.sh --coordinadora && [ \$(grep -c 'hermes-seo:inicio' $H/SOUL.md) = 1 ]"

# ── encargado ──
$HOME/.local/bin/hseo alta web web.com --nombre 'La Web' >/dev/null
si "crear el encargado" "bash $S/actual/encargado.sh crear web"
si "su carta con la web" "grep -q 'Encargado de La Web' $H/profiles/seo-p-web/SOUL.md && grep -q 'hseo estado web' $H/profiles/seo-p-web/SOUL.md"
si "wiki de la web y global, con git propio" "[ -d $S/clientes/web/wiki/.git ] && [ -f $S/clientes/web/wiki/SCHEMA.md ] && [ -d $S/wiki/.git ]"
si "WIKI_PATH en su .env, sin el token del bot" "grep -q 'WIKI_PATH=$S/clientes/web/wiki' $H/profiles/seo-p-web/.env && ! grep -q TELEGRAM $H/profiles/seo-p-web/.env"
si "guardia aprobado con ámbito de su web" "jq -e '.approvals[0].command | test(\"guardia.py web \")' $H/profiles/seo-p-web/shell-hooks-allowlist.json"
si "vigilancia sin modelo: cron cada 5 min, sin vigía con modelo" "grep -q 'seo-p-web cron create \*/5 \* \* \* \* --name hseo-vigilancia --no-agent' $FALSO_LLAMADAS && ! grep -q 'monitor-script vigia.sh' $FALSO_LLAMADAS && [ -x $H/profiles/seo-p-web/scripts/hseo-vigilancia.sh ]"
si "el script de la vigilancia funciona (sin incidencias: nada)" "[ -z \"\$(bash $H/profiles/seo-p-web/scripts/hseo-vigilancia.sh)\" ]"
si "registrado en encargados.json" "jq -e '.web == \"seo-p-web\"' $S/encargados.json"
si "tema: ruta por chat y tema al encargado" "bash $S/actual/encargado.sh tema web 12345 77 && jq -e '.[0].profile == \"seo-p-web\" and .[0].thread_id == \"77\"' $T/rutas"
si "tema: la web sabe dónde avisar" "$HOME/.local/bin/hseo clientes >/dev/null && jq -e '.telegram.thread_id == \"77\"' $S/clientes/web/cliente.json"
si "tema: la vigilancia avisa en el tema" "grep -q -- '--deliver telegram:12345:77' $FALSO_LLAMADAS"
si "tema dos veces no duplica la ruta" "bash $S/actual/encargado.sh tema web 12345 77 && [ \$(jq length $T/rutas) = 1 ]"
si "la foto del encargado" "python3 $S/actual/plugin/hermes-seo/hseo_encargado.py foto web | grep -q 'Desde tu última sesión'"
si "tareas periódicas: datos todos los días (sin búsqueda configurada no hay métricas)" "grep -q 'seo-p-web cron create 0 6 \* \* \* --name hseo-datos --no-agent' $FALSO_LLAMADAS && ! grep -q 'hseo-metricas-semanales' $FALSO_LLAMADAS && grep -q 'hseo-radar' $FALSO_LLAMADAS"
si "el script de la tarea lanza con hseo" "grep -q 'hseo_cli.py lanzar web radar' $H/profiles/seo-p-web/scripts/hseo-radar.sh && grep -q 'datos recoger web' $H/profiles/seo-p-web/scripts/hseo-datos.sh"
$HOME/.local/bin/hseo config web capacidades.busqueda.bing https://web.com/ >/dev/null
$HOME/.local/bin/hseo config web crons '{"radar": null, "visibilidad-ia": "0 9 1 * *", "revision-mensual": "malo"}' >/dev/null
si "un horario mal escrito se rechaza" "! bash $S/actual/encargado.sh crons web"
$HOME/.local/bin/hseo config web crons '{"radar": null, "visibilidad-ia": "0 9 1 * *"}' >/dev/null
: > $FALSO_LLAMADAS
si "crons: con Bing hay métricas; radar desactivado; visibilidad solo si se activa (y sin preguntas no hay pipeline… pero sí la tarea)" "bash $S/actual/encargado.sh crons web && grep -q 'hseo-metricas-semanales' $FALSO_LLAMADAS && ! grep -q 'hseo-radar' $FALSO_LLAMADAS && grep -q 'hseo-visibilidad-ia' $FALSO_LLAMADAS && [ ! -f $H/profiles/seo-p-web/scripts/hseo-radar.sh ]"
si "en la zona horaria de la web" "grep -q -- '--timezone Europe/Madrid' $FALSO_LLAMADAS"
si "reinstalar pone al día los encargados" "bash $ROOT/instalar.sh > $T/salida; grep -q 'Encargado de web al día' $T/salida"
# crons reconciliados por nombre: reinstalar no cambia los ids; lo que sobra se quita
J=$H/profiles/seo-p-web/cron/jobs.json
ANTES=$(jq -c '[.jobs[] | select(.name | startswith("hseo-"))] | sort_by(.name)' $J)
si "hay crons hseo- en el perfil del encargado" "[ \"\$(jq length <<< '$ANTES')\" -gt 0 ]"
si "otra vez crons: mismos ids, ninguno nuevo ni perdido" "bash $S/actual/encargado.sh crons web && [ \"\$(jq -c '[.jobs[] | select(.name | startswith(\"hseo-\"))] | sort_by(.name)' $J)\" = '$ANTES' ]"
python3 - "$J" <<'PY'
import json, sys
d = json.load(open(sys.argv[1])); d["jobs"].append({"id": "viejo123", "name": "hseo-sobra"}); json.dump(d, open(sys.argv[1], "w"))
PY
si "un hseo- que ya no está en el plan se quita" "bash $S/actual/encargado.sh crons web && ! grep -q hseo-sobra $J"

# volver a la instalación anterior sin tocar datos
ANT=$(readlink $S/actual); cp -a "$ANT" "$S/0.0.9-viejo"; echo "# viejo" >> "$S/0.0.9-viejo/plugin/hermes-seo/plugin.yaml"
si "volver.sh reapunta actual y recopia el plugin al principal y al encargado" "bash $ROOT/volver.sh 0.0.9-viejo --sin-reinicio && [ \"\$(readlink $S/actual)\" = $S/0.0.9-viejo ] && grep -q '# viejo' $H/plugins/hermes-seo/plugin.yaml && grep -q '# viejo' $H/profiles/seo-p-web/plugins/hermes-seo/plugin.yaml"
si "y sin argumento vuelve a la de antes" "bash $ROOT/volver.sh --sin-reinicio && [ \"\$(readlink $S/actual)\" = $ANT ] && ! grep -q '# viejo' $H/plugins/hermes-seo/plugin.yaml"
si "rechaza una carpeta que no es una instalación" "! bash $ROOT/volver.sh /tmp --sin-reinicio"
exit $fail
