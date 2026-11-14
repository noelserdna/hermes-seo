#!/usr/bin/env bash
# claude-busca con un Claude Code falso: pregunta cada pregunta N veces, saca las URL citadas y nunca imprime la sesión.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" CLAUDE_BIN="$T/claude"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
python3 "$ROOT/plugin/hermes-seo/hseo_clientes.py" alta web web.com >/dev/null
printf '# Preguntas\n\n1. ¿Mejor curso de X?\n2. ¿Dónde aprendo Y?\n' > "$HERMES_SEO_HOME/clientes/web/preguntas-decision.md"
cat > "$T/claude" <<'C'
#!/usr/bin/env bash
echo "$CLAUDE_CODE_OAUTH_TOKEN" > "${0%/*}/token-visto"
case "$2" in *Y*) echo '{"is_error": true, "result": "rate limit"}'; exit 1;; esac
echo '{"is_error": false, "result": "Te recomiendo web.com.\nSOURCES:\nhttps://web.com/curso\nhttps://otra.com/x.", "total_cost_usd": 0.02}'
C
chmod +x "$T/claude"
echo "CLAUDE_CODE_OAUTH_TOKEN=secreto-sesion" > "$HERMES_SEO_HOME/clientes/web/secretos.env"
out=$("$ROOT/herramientas/claude-busca" --cliente web 2>&1); rc=$?
F="$HERMES_SEO_HOME/clientes/web/datos/ia/claude-$(date +%Y-%m-%d).json"
[ $rc = 1 ] && echo "$out" | grep -q "CLAUDE_ERROR incompleto: 2 respuestas de 4" && ok "incompleto si alguna pregunta falla (código 1)" || bad "incompleto ($rc: $out)"
jq -e '.filas[0].citas == ["https://otra.com/x","https://web.com/curso"]' "$F" >/dev/null && ok "saca las URL citadas" || bad "citas"
[ "$(cat "$T/token-visto")" = secreto-sesion ] && ok "usa la sesión de la web" || bad "sesión"
grep -q secreto-sesion "$F" || ! echo "$out" | grep -q secreto-sesion && ok "no imprime ni guarda la sesión" || bad "sesión impresa"
exit $fail
