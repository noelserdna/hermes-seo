#!/usr/bin/env bash
# Modelos por etapa (perfil → global → cliente; formato por ejecutor y proveedor) y pipelines (validación, plan por
# capacidades del cliente, políticas: pausa, congelación, tope semanal, excepción).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HOME="$T/casa"; mkdir -p "$HOME/.hermes/profiles/seo-redactor" "$HOME/.hermes/profiles/seo-gpt"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
C="python3 $P/hseo_clientes.py"; M="python3 $P/hseo_modelos.py"; PL="python3 $P/hseo_pipelines.py"
igual() { [ "$2" = "$3" ] && ok "$1" || bad "$1 (salió «$2», esperaba «$3»)"; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }

$C alta web web.com --estado repo >/dev/null
printf 'model:\n  default: claude-sonnet-5-5\n  provider: anthropic\n' > "$HOME/.hermes/profiles/seo-redactor/config.yaml"
printf 'model:\n  provider: openai-codex\n  default: gpt-6-sol\n' > "$HOME/.hermes/profiles/seo-gpt/config.yaml"
mkdir -p "$HOME/.hermes/profiles/seo-comentado"
printf 'model:\n  # Default model\n  default: "claude-sonnet-5-5"\n\n  # Inference provider:\n  #   "auto" - x\n  provider: "anthropic"\nterminal:\n  provider: otro\n' > "$HOME/.hermes/profiles/seo-comentado/config.yaml"

# ── modelos ──
igual "equilibrado: redactar con Opus en Claude Code" "$($M para redactar claude)" opus
igual "equilibrado: verificar con Sonnet" "$($M para verificar claude)" sonnet
igual "etapa desconocida: el ligero" "$($M para inventada claude)" sonnet
igual "Hermes con Anthropic directo: id de Anthropic" "$($M para redactar hermes --perfil seo-redactor)" claude-opus-5-5
igual "Hermes con OpenRouter: id de OpenRouter" "$($M para verificar hermes --proveedor openrouter)" anthropic/claude-sonnet-5.5
igual "config con comentarios y líneas en blanco" "$($M para redactar hermes --perfil seo-comentado)" claude-opus-5-5
igual "Hermes con ChatGPT: no fuerza modelo" "$($M para redactar hermes --perfil seo-gpt)" ""
si "perfil calidad" "$M perfil calidad"
igual "calidad: verificar con Opus" "$($M para verificar claude)" opus
si "cambio global de una etapa" "$M poner verificar fable"
igual "el global manda sobre el perfil" "$($M para verificar claude)" fable
si "cambio del cliente" "$M poner verificar sonnet --cliente web"
igual "el del cliente manda sobre el global" "$($M para verificar claude --cliente web)" sonnet
igual "otro cliente sigue con el global" "$($M para verificar claude)" fable
no "Haiku no en una etapa de juicio" "$M poner redactar haiku"
no "modelo con caracteres raros" "$M poner verificar 'rm -rf'"
si "quitar el cambio del cliente" "$M poner verificar - --cliente web"
igual "sin cambio del cliente vuelve al global" "$($M para verificar claude --cliente web)" fable
igual "id completo de OpenRouter a Claude Code" "$($M poner aplicar-cambio anthropic/claude-opus-5.5 >/dev/null; $M para aplicar-cambio claude)" claude-opus-5-5

# ── pipelines ──
si "todas las pipelines del plugin son válidas" "$PL validar-todas"
no "una web sin publicación no lanza un artículo" "$PL plan articulo --cliente web"
$C config web capacidades.publicacion '{"adaptador":"repo-pr","repo":"/tmp/r"}' >/dev/null
si "con repo-pr sí" "$PL plan articulo --cliente web"
si "estrategia sin competidores se salta esa etapa" "$PL plan estrategia --cliente web | grep -q 'competencia.*se salta'"
$C config web competidores '["otra.com"]' >/dev/null
si "con competidores, la etapa corre" "$PL plan estrategia --cliente web | grep -q '▶ competencia'"
no "métricas sin GSC, Bing ni analítica: no" "$PL plan metricas-semanales --cliente web"
$C config web capacidades.busqueda.bing https://web.com/ >/dev/null
si "métricas con Bing basta (requiere gsc|bing|analitica)" "$PL plan metricas-semanales --cliente web"
mkdir -p "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines"
cat > "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines/radar.json" <<'J'
{"id":"radar","nombre":"Radar propio","etapas":[{"id":"radar","titulo":"Radar propio","perfil":"seo-investigador","skill":"radar-propio","ejecutor":"hermes"}]}
J
si "la pipeline del cliente sustituye a la del plugin" "$PL ver radar --cliente web | grep -q radar-propio"
si "otros clientes ven la del plugin" "$C alta otra otra.com >/dev/null; $PL ver radar --cliente otra | grep -q '\"skill\": \"radar\"'"
cat > "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines/mala.json" <<'J'
{"id":"mala","nombre":"Mala","etapas":[{"id":"x","titulo":"{nada}","perfil":"root","skill":"x y","ejecutor":"bash"}]}
J
no "una pipeline mal escrita no se planifica" "$PL plan mala --cliente web"

python3 - "$P" <<'PY' && ok "políticas: pausa, congelación, tope semanal y excepción" || bad "políticas"
import importlib.util, json, sys
from datetime import date
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_pipelines", Path(sys.argv[1]) / "hseo_pipelines.py")
PL = importlib.util.module_from_spec(spec); sys.modules["hseo_pipelines"] = PL; spec.loader.exec_module(PL)
C = sys.modules["hseo_clientes"] if "hseo_clientes" in sys.modules else PL._cargar("hseo_clientes")
def rechaza(f):
    try: f(); return False
    except PL.Rechazo: return True
hoy = date(2026, 11, 14)
PL.politicas("articulo", "web", hoy=hoy)                        # sin políticas: pasa
C.config("web", "politicas.congelado_hasta", "2026-11-26")
assert rechaza(lambda: PL.politicas("articulo", "web", hoy=hoy))
PL.politicas("actualizacion", "web", hoy=hoy)                   # actualizar sí se puede
PL.politicas("articulo", "web", excepcion=True, hoy=hoy)        # excepción pedida por una persona
PL.politicas("articulo", "web", hoy=date(2026, 11, 26))         # el día que acaba ya se puede
C.config("web", "politicas.congelado_hasta", "")
C.config("web", "politicas.tope_semanal", 1)
f = C.carpeta("web") / "encargos.jsonl"
f.write_text(json.dumps({"ts": "2026-11-12T10:00:00Z", "nueva_pieza": True}) + "\n")
assert rechaza(lambda: PL.politicas("articulo", "web", hoy=hoy))
f.write_text(json.dumps({"ts": "2026-11-01T10:00:00Z", "nueva_pieza": True}) + "\n")
PL.politicas("articulo", "web", hoy=hoy)                        # la de hace dos semanas no cuenta
C.config("web", "politicas.pausado", True)
assert rechaza(lambda: PL.politicas("actualizacion", "web", hoy=hoy))
assert rechaza(lambda: PL.politicas("articulo", "web", excepcion=True, hoy=hoy))   # la pausa no tiene excepción
PY
exit $fail
