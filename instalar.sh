#!/usr/bin/env bash
# Instala (o actualiza) hermes-seo en este Hermes. Idempotente: nunca borra perfiles, claves, clientes ni datos.
#
#   bash instalar.sh [--coordinadora | --coordinadora-estricta] [--seco]
#
#   --coordinadora            el perfil principal (default) pasa a ser también la coordinadora: su carta en SOUL.md y
#                             prohibiciones duras (approvals.deny) solo para lo irreversible: decidir o firmar puertas,
#                             secretos y aprobadores. Conserva su terminal: «ojos y manos en todo».
#   --coordinadora-estricta   además, el guardia (fail-closed) que la limita a la CLI hseo y a leer.
#
# Qué deja:
#   ~/.hermes/hermes-seo/<versión> + enlace «actual», instalacion.json, aprobadores.json (si no existe)
#   el plugin hermes-seo activado (Telegram, notario, sección de prompt) y la CLI hseo en ~/.local/bin
#   perfiles: seo-estacion (mueve tarjetas) y los de rol (seo-investigador, seo-redactor, seo-verificador,
#   seo-editor, seo-analista), con sus cartas y las skills del arnés
#   los encargados que ya existían, al día (encargado.sh crear)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HH="$HOME/.hermes"; HSEO="${HERMES_SEO_HOME:-$HH/hermes-seo}"
HERMES="${HERMES_BIN:-hermes}"
COORD=false; ESTRICTA=false; SECO=false
for a in "$@"; do case $a in --coordinadora) COORD=true ;; --coordinadora-estricta) COORD=true; ESTRICTA=true ;;
  --seco) SECO=true ;; *) sed -n '2,18p' "$0"; exit 2 ;; esac; done

falta=()
for c in jq rsync git python3; do command -v "$c" >/dev/null || falta+=("$c"); done
command -v "$HERMES" >/dev/null || [ -x "$HERMES" ] || falta+=(hermes)
[ ${#falta[@]} -eq 0 ] || { echo "Faltan: ${falta[*]}" >&2; exit 1; }
command -v claude >/dev/null || [ -x "$HOME/.npm-global/bin/claude" ] || echo "AVISO: no encuentro Claude Code: las etapas con ejecutor «claude» fallarán"
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)' || { echo "Hace falta python3 >= 3.9" >&2; exit 1; }

VERSION=$(sed -nE 's/^version: *//p' "$ROOT/plugin/hermes-seo/plugin.yaml")
# una carpeta por versión Y commit: la instalación anterior queda intacta para volver (volver.sh)
REV=$(git -C "$ROOT" rev-parse --short HEAD 2>/dev/null || date -u +%Y%m%d%H%M%S)
[ -z "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ] || REV="$REV-local"
DEST="$HSEO/$VERSION-$REV"
ANTERIOR=$(readlink "$HSEO/actual" 2>/dev/null || true)
echo "hermes-seo $VERSION → $DEST"
$SECO && { echo "(en seco: no se cambia nada)"; exit 0; }

# ── 1. el arnés, versionado ─────────────────────────────────────────────────────────────────────────────────────────
mkdir -p "$DEST" "$HSEO/clientes" "$HSEO/puertas"
rsync -a --delete --exclude .git --exclude tests --exclude evals --exclude '__pycache__' "$ROOT/" "$DEST/"
ln -sfn "$DEST" "$HSEO/actual"
ARNES="$HSEO/actual"
for d in "$HH/hermes-agent/optional-skills/research/llm-wiki" "$HH/skills/research/llm-wiki"; do
  if [ -f "$d/SKILL.md" ]; then mkdir -p "$DEST/encargado/skills"; rsync -a --delete "$d/" "$DEST/encargado/skills/llm-wiki/"; break; fi
done
[ -f "$DEST/encargado/skills/llm-wiki/SKILL.md" ] || echo "AVISO: no encuentro la skill llm-wiki de Hermes: los encargados no tendrán memoria en wiki"
jq -n --arg r "$ARNES" --arg v "$VERSION" --arg c "$DEST" --arg a "$ANTERIOR" \
  '{root: $r, version: $v, carpeta: $c, anterior: $a}' > "$HSEO/instalacion.json"

# ── 2. quién decide ─────────────────────────────────────────────────────────────────────────────────────────────────
if [ ! -f "$HSEO/aprobadores.json" ]; then
  TG=$(grep -h '^TELEGRAM_ALLOWED_USERS=' "$HH/.env" 2>/dev/null | cut -d= -f2- | tr -d '"'"'" | cut -d, -f1 || true)
  jq -n --arg u "$(id -un)" --arg t "$TG" '{yo: {nombre: $u, canales: ({local: $u, dashboard: $u} + (if $t != "" then {telegram: $t} else {} end)), clientes: ["*"]}}' \
    > "$HSEO/aprobadores.json"
  chmod 600 "$HSEO/aprobadores.json"
  echo "Creado aprobadores.json (tú decides en todas las webs${TG:+; Telegram $TG})"
fi

# ── 3. el plugin y la CLI ───────────────────────────────────────────────────────────────────────────────────────────
mkdir -p "$HH/plugins" "$HOME/.local/bin"
rm -rf "$HH/plugins/hermes-seo"
cp -R "$DEST/plugin/hermes-seo" "$HH/plugins/hermes-seo"
"$HERMES" plugins enable hermes-seo >/dev/null 2>&1 || echo "AVISO: no pude activar el plugin (hermes plugins enable hermes-seo)"
ln -sfn "$ARNES/hseo" "$HOME/.local/bin/hseo"
# Hermes carga los plugins por perfil: sin esta copia el encargado no recibe la foto de su web en el prompt
for PD in "$HH"/profiles/seo-p-*; do
  [ -d "$PD" ] || continue
  mkdir -p "$PD/plugins"; rm -rf "$PD/plugins/hermes-seo"; cp -R "$DEST/plugin/hermes-seo" "$PD/plugins/hermes-seo"
  "$HERMES" -p "$(basename "$PD")" plugins enable hermes-seo >/dev/null 2>&1 \
    || echo "AVISO: no pude activar el plugin en $(basename "$PD")"
done

# ── 4. perfiles ─────────────────────────────────────────────────────────────────────────────────────────────────────
existe() { "$HERMES" profile list 2>/dev/null | grep -qw "$1"; }
copiar_modelo() {  # mismo proveedor y modelo que el perfil principal; solo las claves del proveedor (nunca las del bot)
  local P=$1 PD="$HH/profiles/$1" k v
  for k in provider base_url api_mode default; do
    v=$("$HERMES" config get "model.$k" 2>/dev/null | tail -1 || true)
    [ -n "$v" ] && [ "$v" != None ] && "$HERMES" -p "$P" config set "model.$k" "$v" >/dev/null || true
  done
  mkdir -p "$PD"
  { grep -hE '^(OPENROUTER_API_KEY|ANTHROPIC_API_KEY|CLAUDE_CODE_OAUTH_TOKEN|OPENAI_API_KEY)=' "$HH/.env" 2>/dev/null || true
    echo "HERMES_SEO_HOME=$HSEO"; } > "$PD/.env"
  chmod 600 "$PD/.env"
}
carta() {  # SOUL.md = carta del perfil + reglas comunes (con copia de la anterior)
  local PD="$HH/profiles/$1"
  mkdir -p "$PD"
  [ -f "$PD/SOUL.md" ] && ! cmp -s "$PD/SOUL.md" <(cat "$ROOT/perfiles/$1.md" "$ROOT/perfiles/comun.md") && cp "$PD/SOUL.md" "$PD/SOUL.md.bak-$(date +%Y%m%d%H%M%S)"
  cat "$ROOT/perfiles/$1.md" "$ROOT/perfiles/comun.md" > "$PD/SOUL.md"
}
skills_dirs() {  # las skills del arnés y las propias de cada web (clientes/<web>/extensiones/skills)
  { echo "$ARNES/skills"; for d in "$HSEO"/clientes/*/extensiones/skills; do [ -d "$d" ] && echo "$d"; done; } | jq -Rnc '[inputs]'
}
DENY='["*hseo_puertas.py*","*hseo_encargos.py*","*hseo_clientes.py*","*decidir-local*","*aprobadores.json*","*secretos.env*","*hermes config*","*hermes cron*","*hermes kanban*","*sqlite3*","*git push*","*wrangler deploy*"]'

if ! existe seo-estacion; then
  "$HERMES" profile create seo-estacion --no-alias --no-skills \
    --description "Estación de hermes-seo: ejecuta etapa.sh de cada tarjeta y mueve la tarjeta según el resultado. No decide nada." >/dev/null
  copiar_modelo seo-estacion
fi
carta seo-estacion
"$HERMES" -p seo-estacion tools disable web browser image_gen tts computer_use cronjob delegation code_execution connections memory >/dev/null 2>&1 || true
# Hermes corta los comandos en primer plano a los 420 s salvo que el perfil suba TERMINAL_MAX_FOREGROUND_TIMEOUT
# (en .env) y timeouts.tools.*: sin esto, una etapa de Claude de más de 7 min se pierde (pasó con el caso, 14-11).
env_linea() {   # env_linea <perfil> <CLAVE> <valor>: pone o cambia la línea sin tocar el resto del .env
  local f="$HH/profiles/$1/.env"; touch "$f"; chmod 600 "$f"
  grep -v "^$2=" "$f" > "$f.tmp" || true; echo "$2=$3" >> "$f.tmp"; mv "$f.tmp" "$f"; chmod 600 "$f"
}
env_linea seo-estacion TERMINAL_MAX_FOREGROUND_TIMEOUT 9600
for kv in "terminal.timeout 9600" "terminal.lifetime_seconds 9600" "timeouts.tools.sequential_call 9600" \
          "timeouts.tools.concurrent_batch 9600" "curator.enabled false" "display.language es"; do
  "$HERMES" -p seo-estacion config set $kv >/dev/null 2>&1 || true
done
"$HERMES" -p seo-estacion config set approvals.deny "$DENY" >/dev/null 2>&1 || true

for P in seo-investigador seo-redactor seo-verificador seo-editor seo-analista; do
  if ! existe "$P"; then
    "$HERMES" profile create "$P" --no-alias --no-skills \
      --description "$(sed -n '1s/^# //p' "$ROOT/perfiles/$P.md") de hermes-seo: hace etapas de pipelines (no decide ni publica)." >/dev/null
    copiar_modelo "$P"
  fi
  carta "$P"
  "$HERMES" -p "$P" config set skills.external_dirs "$(skills_dirs)" >/dev/null 2>&1 || true
  "$HERMES" -p "$P" config set approvals.deny "$DENY" >/dev/null 2>&1 || true
  "$HERMES" -p "$P" tools disable cronjob delegation >/dev/null 2>&1 || true
  env_linea "$P" TERMINAL_MAX_FOREGROUND_TIMEOUT 2400
  for kv in "terminal.timeout 2400" "terminal.lifetime_seconds 2400" "timeouts.tools.sequential_call 2400" \
            "timeouts.tools.concurrent_batch 2400" "display.language es"; do
    "$HERMES" -p "$P" config set $kv >/dev/null 2>&1 || true
  done
done

# ── 5. la coordinadora (opcional) ───────────────────────────────────────────────────────────────────────────────────
if $COORD; then
  S="$HH/SOUL.md"; touch "$S"; cp "$S" "$S.bak-$(date +%Y%m%d%H%M%S)"
  python3 - "$S" "$ROOT/perfiles/coordinadora.md" <<'PY'
import re, sys
s, nueva = open(sys.argv[1]).read(), open(sys.argv[2]).read().strip()
bloque = f"<!-- hermes-seo:inicio -->\n{nueva}\n<!-- hermes-seo:fin -->"
if "<!-- hermes-seo:inicio -->" in s:
    s = re.sub(r"<!-- hermes-seo:inicio -->.*?<!-- hermes-seo:fin -->", lambda m: bloque, s, flags=re.S)
else:
    s = s.rstrip() + "\n\n" + bloque + "\n"
open(sys.argv[1], "w").write(s)
PY
  # lo irreversible nunca, ni siquiera con la terminal libre (se suma a lo que ya hubiera en approvals.deny)
  ACTUAL=$("$HERMES" config get approvals.deny --json 2>/dev/null || echo '[]'); jq -e 'type == "array"' <<< "$ACTUAL" >/dev/null 2>&1 || ACTUAL='[]'
  "$HERMES" config set approvals.deny "$(jq -c '. + ["*hseo_puertas.py*","*decidir-local*","*/puertas/g*","*aprobadores.json*","*hermes-seo/secretos.env*"] | unique' <<< "$ACTUAL")" >/dev/null
  echo "Coordinadora: carta añadida a $S; lo irreversible (decidir puertas, aprobadores, secretos) prohibido"
  # salud del servidor: revisar FUERA de Hermes (crontab del usuario) y avisar desde un cron sin IA de la coordinadora
  LINEA="*/10 * * * * HERMES_SEO_HOME=$HSEO python3 $HSEO/actual/plugin/hermes-seo/hseo_sistema.py revisar >> $HSEO/sistema.log 2>&1"
  if [ -z "${HSEO_SIN_CRONTAB:-}" ] && command -v crontab >/dev/null && ! crontab -l 2>/dev/null | grep -q "hseo_sistema.py revisar"; then
    { crontab -l 2>/dev/null; echo "$LINEA"; } | crontab - && echo "Sistema: revisión cada 10 min en el crontab"
  fi
  mkdir -p "$HH/scripts"
  printf '#!/usr/bin/env bash\nexport HERMES_SEO_HOME=%q PATH="$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"\nexec python3 %q avisos\n' \
    "$HSEO" "$HSEO/actual/plugin/hermes-seo/hseo_sistema.py" > "$HH/scripts/hseo-sistema.sh"; chmod +x "$HH/scripts/hseo-sistema.sh"
  TEMAS=$("$HERMES" config get platforms.telegram.extra.dm_topics --json 2>/dev/null || echo '[]')
  DEST=$(jq -r 'first(.[]? | .chat_id as $c | .topics[]? | select(.name | test("Sistema|Cartera")) | "telegram:\($c):\(.thread_id)") // "telegram"' <<< "$TEMAS" 2>/dev/null || echo telegram)
  ID=$(jq -r '(if type == "array" then . else (.jobs // []) end)[] | select(.name == "hseo-sistema") | .id' "$HH/cron/jobs.json" 2>/dev/null | head -1 || true)
  if [ -n "$ID" ]; then
    "$HERMES" cron edit "$ID" --schedule "*/10 * * * *" --no-agent --script hseo-sistema.sh --deliver "$DEST" --catch-up off >/dev/null || echo "AVISO: no pude actualizar hseo-sistema"
  else
    "$HERMES" cron create "*/10 * * * *" --name hseo-sistema --no-agent --script hseo-sistema.sh --deliver "$DEST" --catch-up off >/dev/null \
      || echo "AVISO: no pude crear el cron hseo-sistema"
  fi
  "$HERMES" config set cron.wrap_response false >/dev/null || true
  echo "Sistema: avisos sin IA en $DEST (solo lo que no se arregla solo)"
fi
if $ESTRICTA; then
  GUARDIA="python3 -I $ARNES/encargado/guardia.py cartera $ARNES"
  "$HERMES" config set hooks.pre_tool_call \
    "[{\"matcher\":\"terminal|write_file|patch|read_file|execute_code|delegate_task\",\"command\":\"$GUARDIA\",\"timeout\":10,\"fail_closed\":true}]" >/dev/null
  python3 - "$HH/shell-hooks-allowlist.json" "$GUARDIA" <<'PY'
import json, sys, datetime
f, c = sys.argv[1:]
try:
    d = json.load(open(f))
except (OSError, ValueError):
    d = {"approvals": []}
d["approvals"] = [a for a in d.get("approvals", []) if "encargado/guardia.py cartera" not in a.get("command", "")]
d["approvals"].append({"event": "pre_tool_call", "command": c, "approved_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")})
json.dump(d, open(f, "w"), indent=2)
PY
  echo "Coordinadora estricta: guardia activo (solo hseo y lectura)"
fi

# ── 6. encargados existentes, al día ────────────────────────────────────────────────────────────────────────────────
for slug in $(jq -r 'keys[]' "$HSEO/encargados.json" 2>/dev/null || true); do
  bash "$ARNES/encargado.sh" crear "$slug" >/dev/null && echo "Encargado de $slug al día"
done

# ── 7. avisos de configuración ──────────────────────────────────────────────────────────────────────────────────────
v=$("$HERMES" config get kanban.dispatch_interval_seconds 2>/dev/null | tail -1 || true)
[ -n "$v" ] && [ "$v" -gt 15 ] 2>/dev/null && echo "AVISO: las etapas tardan hasta ${v}s en arrancar: hermes config set kanban.dispatch_interval_seconds 10"
v=$("$HERMES" config get kanban.auto_decompose 2>/dev/null | tail -1 || true)
[ "$v" = true ] && echo "AVISO: kanban.auto_decompose está activo: hermes config set kanban.auto_decompose false"
echo "Listo. Reinicia el gateway (hermes gateway restart o el servicio) para cargar el plugin."
