#!/usr/bin/env bash
# El ENCARGADO de una web (perfil de Hermes seo-p-<web>): conversa, vigila, lanza trabajo con hseo y recuerda en la
# wiki de la web. No decide ni publica. Copiado y adaptado de hermes-sdd (encargado.sh).
#
#   encargado.sh crear <web>                      perfil, carta (SOUL), guardia, wiki y vigía (idempotente)
#   encargado.sh tema <web> <chat_id> <thread_id>  ese tema de Telegram habla con el encargado (profile_routes)
#   encargado.sh skills <web>                      los perfiles de rol ven las skills propias de las webs
#   encargado.sh crons <web>                       tareas periódicas de la web (datos, radar, métricas…) en su perfil
#   encargado.sh borrar <web>                      quita el perfil y su ruta (la wiki y los datos se quedan)
#   encargado.sh perfil <web>                      nombre del perfil
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HH="$HOME/.hermes"; HSEO="${HERMES_SEO_HOME:-$HH/hermes-seo}"
CMD=${1:-}; SLUG=${2:-}; [ -n "$SLUG" ] || { sed -n '2,10p' "$0" >&2; exit 2; }
P="seo-p-$SLUG"
ARNES="$HSEO/actual"; [ -d "$ARNES" ] || ARNES=$ROOT
CARPETA="$HSEO/clientes/$SLUG"
HERMES="${HERMES_BIN:-hermes}"
PYC="python3 $ARNES/plugin/hermes-seo/hseo_clientes.py"

[ "$CMD" = perfil ] && { echo "$P"; exit 0; }
[ -f "$CARPETA/cliente.json" ] || { echo "ERROR: no conozco la web $SLUG (hseo alta)" >&2; exit 1; }
NOMBRE=$(jq -r '.nombre' "$CARPETA/cliente.json"); URL=$(jq -r '.url' "$CARPETA/cliente.json")

registrar() {  # encargados.json: web → perfil (lo lee el plugin)
  python3 - "$HSEO/encargados.json" "$SLUG" "$1" <<'PY'
import json, sys
f, slug, perfil = sys.argv[1:]
try:
    d = json.load(open(f))
except (OSError, ValueError):
    d = {}
if perfil:
    d[slug] = perfil
else:
    d.pop(slug, None)
json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
PY
}

wiki() {  # wiki de la web (llm-wiki) como repositorio git propio, y la global si aún no existe
  local W="$1" titulo="$2" hoy; hoy=$(date +%Y-%m-%d)
  mkdir -p "$W/raw/documentos" "$W/raw/capturas" "$W/entities" "$W/concepts" "$W/comparisons" "$W/queries"
  [ -f "$W/SCHEMA.md" ] || sed "s|{{WEB}}|$titulo|g" "$ROOT/encargado/wiki/SCHEMA.md" > "$W/SCHEMA.md"
  [ -f "$W/index.md" ] || printf '# Wiki — %s\n\n> Memoria. Ver SCHEMA.md.\n\n## Entities\n\n## Concepts\n\n## Comparisons\n\n## Queries\n' "$titulo" > "$W/index.md"
  [ -f "$W/log.md" ] || printf '# Log — %s\n\n> Actions: ingest, update, query, lint, create, archive, delete\n\n## [%s] create | Wiki initialized\n' "$titulo" "$hoy" > "$W/log.md"
  for d in raw/documentos raw/capturas entities concepts comparisons queries; do [ -n "$(ls -A "$W/$d")" ] || touch "$W/$d/.gitkeep"; done
  if [ ! -d "$W/.git" ]; then
    git -C "$W" init -q && git -C "$W" add -A && git -C "$W" -c user.name="hermes-seo" -c user.email="wiki@hermes-seo" commit -qm "Wiki: $titulo"
  fi
}

vigilante() {  # cron del vigía en el perfil: cada 5 min un script sin LLM; el modelo solo despierta si su salida cambia
  local PD="$HH/profiles/$P" id destino
  mkdir -p "$PD/scripts"
  cat > "$PD/scripts/vigia.sh" <<V
export PATH="$(dirname "$(command -v "$HERMES" 2>/dev/null || echo /usr/bin/hermes)"):/usr/local/bin:/usr/bin:/bin"
export HERMES_SEO_HOME="$HSEO"
exec python3 "$ARNES/plugin/hermes-seo/hseo_encargado.py" vigia "$SLUG"
V
  chmod +x "$PD/scripts/vigia.sh"
  destino=$(jq -r 'if (.telegram.chat_id // "") != "" then "telegram:\(.telegram.chat_id):\(.telegram.thread_id)" else "telegram" end' "$CARPETA/cliente.json")
  local PROMPT="Eres el encargado de $NOMBRE y te despierta el vigía: cambió la lista de asuntos que mirar (va arriba, MONITOR CHANGE). Para cada asunto NUEVO, diagnostica con hseo (estado, encargos, puertas) y los ficheros de la web, y actúa según tu carta, sección «Cuando te despierta el vigía». En esta ronda no hay nadie para aprobar: lo que necesite aprobación, recomiéndalo. Después escribe a la persona un mensaje breve en castellano: qué pasó, qué hiciste o qué recomiendas, y qué necesitas que decida. Si lo único que cambió es que algo se resolvió, una línea. Si no hay nada que contar, responde exactamente [SILENT]."
  id=$(jq -r '(if type == "array" then . else (.jobs // []) end)[] | select(.name == "vigia") | .id' "$PD/cron/jobs.json" 2>/dev/null | head -1 || true)
  if [ -n "$id" ]; then
    "$HERMES" -p "$P" cron edit "$id" --schedule "every 5m" --prompt "$PROMPT" --monitor-script vigia.sh --workdir "$CARPETA" --deliver "$destino" >/dev/null
  else
    "$HERMES" -p "$P" cron create "every 5m" "$PROMPT" --name vigia --monitor-script vigia.sh --workdir "$CARPETA" \
      --deliver "$destino" --catch-up off >/dev/null
  fi
  echo "  Vigía: cada 5 min (sin IA salvo si algo cambia), avisa en $destino"
}

tareas() {  # crons de la web en el perfil del encargado (hseo_crons.py plan): se borran los hseo-* y se recrean
  local PD="$HH/profiles/$P" destino tz plan
  mkdir -p "$PD/scripts"
  destino=$(jq -r 'if (.telegram.chat_id // "") != "" then "telegram:\(.telegram.chat_id):\(.telegram.thread_id)" else "telegram" end' "$CARPETA/cliente.json")
  tz=$(jq -r '.zona_horaria' "$CARPETA/cliente.json")
  plan=$(python3 "$ARNES/plugin/hermes-seo/hseo_crons.py" plan "$SLUG") || return 1
  for id in $(jq -r '(if type == "array" then . else (.jobs // []) end)[] | select(.name | startswith("hseo-")) | .id' "$PD/cron/jobs.json" 2>/dev/null || true); do
    "$HERMES" -p "$P" cron remove "$id" >/dev/null 2>&1 || true
  done
  rm -f "$PD"/scripts/hseo-*.sh
  while IFS=$'\t' read -r nombre horario orden; do
    [ -n "$nombre" ] || continue
    # sin salida si todo va bien (no avisa); si falla, el motivo llega al tema de la web
    printf '#!/usr/bin/env bash\nexport HERMES_SEO_HOME=%q HSEO_QUIEN=cron PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"\nsalida=$(python3 %q %s 2>&1) || echo "⚠️ ${salida}"\n' \
      "$HSEO" "$ARNES/plugin/hermes-seo/hseo_cli.py" "$orden" > "$PD/scripts/hseo-$nombre.sh"
    [ "$nombre" = datos ] && printf '#!/usr/bin/env bash\nexport HERMES_SEO_HOME=%q PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"\nexec python3 %q %s\n' \
      "$HSEO" "$ARNES/plugin/hermes-seo/hseo_cli.py" "$orden" > "$PD/scripts/hseo-$nombre.sh"
    chmod +x "$PD/scripts/hseo-$nombre.sh"
    "$HERMES" -p "$P" cron create "$horario" --name "hseo-$nombre" --no-agent --script "hseo-$nombre.sh" \
      --deliver "$destino" --timezone "$tz" --catch-up off >/dev/null
    echo "  ⏰ $nombre: $horario ($tz)"
  done < <(jq -r '.[] | [.nombre, .horario, (.orden | join(" "))] | @tsv' <<< "$plan")
}

case "$CMD" in
  crons) tareas ;;

  skills)   # tras añadir skills propias de la web: los perfiles de rol las ven (skills.external_dirs)
    D=$({ echo "$ARNES/skills"; for d in "$HSEO"/clientes/*/extensiones/skills; do [ -d "$d" ] && echo "$d"; done; } | jq -Rnc '[inputs]')
    for R in seo-investigador seo-redactor seo-verificador seo-editor seo-analista; do
      "$HERMES" -p "$R" config set skills.external_dirs "$D" >/dev/null 2>&1 || true
    done
    echo "Skills de los perfiles de rol: $D" ;;

  crear)
    wiki "$CARPETA/wiki" "$NOMBRE"
    wiki "$HSEO/wiki" "hermes-seo (global)"
    if ! "$HERMES" profile list 2>/dev/null | grep -qw "$P"; then
      "$HERMES" profile create "$P" --no-alias --no-skills \
        --description "Encargado del SEO de $NOMBRE (hermes-seo): conversa, vigila, lanza trabajo con hseo y recuerda en su wiki. No decide ni publica." >/dev/null
    fi
    PD="$HH/profiles/$P"; mkdir -p "$PD"
    sed -e "s|{{WEB}}|$NOMBRE|g" -e "s|{{URL}}|$URL|g" -e "s|{{SLUG}}|$SLUG|g" -e "s|{{CARPETA}}|$CARPETA|g" \
        -e "s|{{GLOBAL}}|$HSEO/wiki|g" -e "s|{{ARNES}}|$ARNES|g" "$ROOT/encargado/SOUL.md" > "$PD/SOUL.md"
    cat "$ROOT/perfiles/comun.md" >> "$PD/SOUL.md"
    for k in provider base_url api_mode default; do   # el mismo proveedor y modelo que la instalación principal
      v=$("$HERMES" config get "model.$k" 2>/dev/null | tail -1 || true)
      [ -n "$v" ] && [ "$v" != None ] && "$HERMES" -p "$P" config set "model.$k" "$v" >/dev/null || true
    done
    M=$(python3 "$ARNES/plugin/hermes-seo/hseo_modelos.py" para encargado hermes --perfil default 2>/dev/null || true)
    [ -n "$M" ] && "$HERMES" -p "$P" config set model.default "$M" >/dev/null || true
    # solo las claves del proveedor del modelo (nunca el token del bot)
    { grep -hE '^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|OPENAI_API_KEY)=' "$HH/.env" 2>/dev/null || true
      echo "WIKI_PATH=$CARPETA/wiki"; echo "HERMES_SEO_HOME=$HSEO"; } > "$PD/.env"; chmod 600 "$PD/.env"
    "$HERMES" -p "$P" tools disable web browser image_gen tts computer_use cronjob delegation code_execution \
      connections kanban >/dev/null 2>&1 || true
    "$HERMES" -p "$P" tools enable terminal file clarify skills memory session_search vision >/dev/null 2>&1 || true
    for kv in "terminal.cwd $CARPETA" "agent.clarify_timeout 1800" "curator.enabled false" "skills.write_approval true" "display.language es"; do
      "$HERMES" -p "$P" config set $kv >/dev/null
    done
    "$HERMES" -p "$P" config set skills.external_dirs "[\"$ARNES/encargado/skills\"]" >/dev/null
    "$HERMES" -p "$P" config set approvals.deny \
      '["*hseo_puertas.py*","*hseo_encargos.py*","*hseo_clientes.py*","*etapa.sh*","*firmar*","*decidir*","*aprobadores.json*","*jev.json*","*secretos.env*","*hermes kanban*","*hermes config*","*hermes cron*","*sqlite3*","*git push*"]' >/dev/null
    GUARDIA="python3 -I $ARNES/encargado/guardia.py $SLUG $ARNES"
    "$HERMES" -p "$P" config set hooks.pre_tool_call \
      "[{\"matcher\":\"terminal|write_file|patch|read_file|execute_code|delegate_task|cronjob\",\"command\":\"$GUARDIA\",\"timeout\":10,\"fail_closed\":true}]" >/dev/null
    jq -n --arg c "$GUARDIA" --arg t "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      '{approvals: [{event: "pre_tool_call", command: $c, approved_at: $t}]}' > "$PD/shell-hooks-allowlist.json"
    registrar "$P"
    echo "Encargado de $NOMBRE listo: perfil $P, wiki en $CARPETA/wiki"
    vigilante
    tareas
    echo "  Hablar con él: /seo_tema $SLUG en Telegram · hermes -p $P chat" ;;

  tema)   # Ruta por chat Y tema (si fuera solo por chat, todo el privado iría al encargado)
    CHAT=${3:?falta el chat_id}; HILO=${4:?falta el thread_id}
    RUTAS=$("$HERMES" config get gateway.profile_routes --json 2>/dev/null || echo '[]')
    TEMAS=$("$HERMES" config get platforms.telegram.extra.dm_topics --json 2>/dev/null || echo '[]')
    jq -e 'type == "array"' <<< "$RUTAS" >/dev/null 2>&1 || RUTAS='[]'; jq -e 'type == "array"' <<< "$TEMAS" >/dev/null 2>&1 || TEMAS='[]'
    RUTAS=$(jq -c --arg n "seo-$SLUG" --arg c "$CHAT" --argjson t "$HILO" --arg p "$P" \
      '[.[] | select(.name != $n)] + [{name: $n, platform: "telegram", chat_id: $c, thread_id: ($t | tostring), profile: $p}]' <<< "$RUTAS")
    TEMAS=$(jq -c --arg c "$CHAT" --argjson t "$HILO" --arg nombre "🧭 $NOMBRE" '
      (if any(.[]; (.chat_id | tostring) == $c) then . else . + [{chat_id: ($c | tonumber), topics: []}] end)
      | map(if (.chat_id | tostring) == $c
            then .topics = ([.topics[]? | select(.name != $nombre and (.thread_id // 0) != $t)] + [{name: $nombre, thread_id: $t}])
            else . end)' <<< "$TEMAS")
    "$HERMES" config set gateway.multiplex_profiles true >/dev/null
    "$HERMES" config set gateway.profile_routes "$RUTAS" >/dev/null
    "$HERMES" config set platforms.telegram.extra.dm_topics "$TEMAS" >/dev/null
    $PYC config "$SLUG" telegram "{\"chat_id\":\"$CHAT\",\"thread_id\":\"$HILO\"}" --quien "encargado.sh tema" >/dev/null
    echo "Tema «🧭 ${NOMBRE}» ($CHAT/$HILO) → $P (se activa al reiniciar el gateway)"
    vigilante
    tareas ;;

  borrar)
    "$HERMES" profile delete -y "$P" >/dev/null 2>&1 || true
    RUTAS=$("$HERMES" config get gateway.profile_routes --json 2>/dev/null || echo '[]')
    if jq -e --arg n "seo-$SLUG" 'any(.[]; .name == $n)' <<< "$RUTAS" >/dev/null 2>&1; then
      "$HERMES" config set gateway.profile_routes "$(jq -c --arg n "seo-$SLUG" '[.[] | select(.name != $n)]' <<< "$RUTAS")" >/dev/null
    fi
    registrar ""
    echo "Perfil $P borrado (la wiki y los datos siguen en $CARPETA)" ;;

  *) sed -n '2,10p' "$0" >&2; exit 2 ;;
esac
