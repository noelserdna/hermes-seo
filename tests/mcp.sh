#!/usr/bin/env bash
# Webs que publican por su propio servidor MCP (auth.md, service_auth): conectar con un código que aprueba una persona,
# renovar el acceso, leer solo con herramientas de lectura y publicar (con su traducción enlazada) al aprobarse una
# puerta. Sin red: tests/dobles/mcp_servidor.py hace de servidor.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HSEO_MCP_DOBLE="$ROOT/tests/dobles/mcp_servidor.py" MCP_DOBLE_ESTADO="$T/servidor.json"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }
C="python3 $ROOT/plugin/hermes-seo/hseo_clientes.py"
X="python3 $ROOT/plugin/hermes-seo/hseo_mcp.py"
W="$HERMES_SEO_HOME/clientes/tour"

$C alta tour web.test --estado repo >/dev/null
no "sin dirección del servidor MCP no se puede conectar" "$X conectar tour ana@web.test"
no "el adaptador mcp exige la dirección https" "$C config tour capacidades.publicacion '{\"adaptador\":\"mcp\"}'"
$C config tour capacidades.publicacion '{"adaptador":"mcp","url":"https://web.test/mcp","guardar":{"herramienta":"guardar_articulo","args":{"idioma":"{idioma}","slug":"{slug}","titulo":"{titulo}","meta_descripcion":"{meta_descripcion}","cuerpo_markdown":"{cuerpo}","publico":"{publico}","traduccion_de":"{traduccion_de}","publicar":true}},"reglas":"Primer párrafo = respuesta"}' >/dev/null
$C config tour idiomas '["es","en"]' >/dev/null

python3 - "$ROOT" <<'PY' && ok "conectar: código para la persona, espera hasta que lo aprueba y guarda el acceso aparte (600)" || bad "conectar"
import importlib.util, os, stat, sys
from pathlib import Path
P = Path(sys.argv[1]) / "plugin/hermes-seo"; sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_mcp", P / "hseo_mcp.py"); X = importlib.util.module_from_spec(s); sys.modules["hseo_mcp"] = X; s.loader.exec_module(X)
r = X.conectar("tour", "Ana@Web.test", esperar_aparte=False)
assert r["codigo"] == "123456" and r["donde"].endswith("/agente/reclamar") and r["correo"] == "ana@web.test", r
assert "esperando" in X.estado("tour")
assert X.esperar("tour", tope_s=30) == "conectado"
d = Path(os.environ["HERMES_SEO_HOME"]) / "clientes/tour/mcp-tokens"
assert stat.S_IMODE((d / "sesion.json").stat().st_mode) == 0o600 and not (d / "pendiente.json").exists()
assert "conectada como ana@web.test" in X.estado("tour")
PY
si "la sesión no está en cliente.json ni en el historial de configuración" "! grep -rq 'asercion-secreta\|tok1' $W/cliente.json $W/config.jsonl"
si "lista las herramientas, marcando las que escriben" "$X herramientas tour | grep -q 'guardar_articulo .*escribe' && $X herramientas tour | grep -q 'despublicar_articulo .*destructiva'"
si "lee con una herramienta de lectura (respuesta en flujo SSE)" "$X llamar tour estadisticas_blog '{\"desde\":\"2026-11-01\"}' | grep -q '\"visitas\": 42'"
no "una herramienta que escribe no se usa desde la CLI ni por un agente" "$X llamar tour guardar_articulo '{\"titulo\":\"x\"}'"

python3 - "$ROOT" <<'PY' && ok "token caducado: se renueva con la aserción, sin volver a preguntar" || bad "renovar"
import importlib.util, json, os, sys
from pathlib import Path
P = Path(sys.argv[1]) / "plugin/hermes-seo"; sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_mcp", P / "hseo_mcp.py"); X = importlib.util.module_from_spec(s); sys.modules["hseo_mcp"] = X; s.loader.exec_module(X)
f = Path(os.environ["HERMES_SEO_HOME"]) / "clientes/tour/mcp-tokens/sesion.json"
d = json.loads(f.read_text()); d["expira"] = 0; f.write_text(json.dumps(d))
assert X.token("tour") == "tok2"
PY

# ── publicar (lo que hace el notario al aprobarse la puerta) ──
d="$W/encargos/enc1"; mkdir -p "$d"
printf -- '---\ntitulo: Cómo ==oír al guía==\nmeta_descripcion: Todo sobre oír al guía\n---\nResumen corto.\n\n## Preguntas frecuentes\n' > "$d/borrador.md"
printf -- '---\ntitulo: How to ==hear the guide==\nmeta_descripcion: All about it\n---\nShort answer.\n' > "$d/borrador-en.md"
echo '{"tipo":"nuevo","url":"https://web.test/es/oir-al-guia","contenido":"borrador.md","idioma":"es","publico":"guias","clase":"articulo","hipotesis":"x","traducciones":[{"idioma":"en","contenido":"borrador-en.md","url":"https://web.test/hear-the-guide"}]}' > "$d/publicacion.json"
pub() { python3 - "$ROOT" "$@" <<'PY'
import importlib.util, sys
from pathlib import Path
P = Path(sys.argv[1]) / "plugin/hermes-seo"; sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_publicacion", P / "hseo_publicacion.py"); M = importlib.util.module_from_spec(s); sys.modules["hseo_publicacion"] = M; s.loader.exec_module(M)
try:
    print(M.publicar(sys.argv[2], sys.argv[3], "Ana (correo)"))
except M.Rechazo as e:
    print("RECHAZO", e); sys.exit(2)
PY
}
R=$(pub tour enc1)
python3 - "$MCP_DOBLE_ESTADO" "$R" <<'PY' && ok "publica la principal y su traducción enlazada, con los argumentos de la plantilla" || bad "publicar: $R"
import json, sys
e = json.load(open(sys.argv[1])); r = sys.argv[2]
g = [l["arguments"] for l in e["llamadas"] if l["name"] == "guardar_articulo"]
assert len(g) == 2, g
es, en = g
assert es["idioma"] == "es" and es["slug"] == "oir-al-guia" and es["titulo"] == "Cómo ==oír al guía==" and es["publicar"] is True
assert es["cuerpo_markdown"].startswith("Resumen corto.") and es["publico"] == "guias" and "traduccion_de" not in es
assert en["idioma"] == "en" and en["slug"] == "hear-the-guide" and en["traduccion_de"] == 101 and en["titulo"].startswith("How to")
assert "es: https://web.test/es/oir-al-guia" in r and "en: https://web.test/hear-the-guide" in r and "meta corta" in r, r
PY
si "queda apuntado en cambios.jsonl y con qué deshacerlo" "grep -q '\"adaptador\": \"mcp\"' $W/cambios.jsonl && jq -e '.principal == 101' $W/encargos/enc1/publicado.json"

d="$W/encargos/enc2"; mkdir -p "$d"; printf -- '---\nmeta_descripcion: x\n---\nCuerpo.\n' > "$d/borrador.md"
echo '{"tipo":"nuevo","url":"https://web.test/es/sin-titulo","contenido":"borrador.md"}' > "$d/publicacion.json"
R=$(pub tour enc2); [ $? = 2 ] && echo "$R" | grep -q "Falta el título" && ok "si la web dice que no, la puerta da el motivo de la web" || bad "error de la web: $R"

d="$W/encargos/enc3"; mkdir -p "$d"
echo '{"tipo":"cambio-tecnico","cambios":[{"accion":"title","url":"https://web.test/precios","antes":"a","despues":"b"}]}' > "$d/publicacion.json"
si "un cambio técnico (páginas fijas) va como entrega a mano" "pub tour enc3 | grep -q 'por MCP solo se publica el blog'"

python3 - "$MCP_DOBLE_ESTADO" <<'PY'
import json, sys
e = json.load(open(sys.argv[1])); e["revocado"] = True; json.dump(e, open(sys.argv[1], "w"))
PY
python3 - "$ROOT" <<'PY' && ok "acceso revocado en la web: se dice que hay que volver a conectar" || bad "revocado"
import importlib.util, json, os, sys
from pathlib import Path
P = Path(sys.argv[1]) / "plugin/hermes-seo"; sys.path.insert(0, str(P))
s = importlib.util.spec_from_file_location("hseo_mcp", P / "hseo_mcp.py"); X = importlib.util.module_from_spec(s); sys.modules["hseo_mcp"] = X; s.loader.exec_module(X)
f = Path(os.environ["HERMES_SEO_HOME"]) / "clientes/tour/mcp-tokens/sesion.json"
d = json.loads(f.read_text()); d["expira"] = 0; f.write_text(json.dumps(d))
try:
    X.token("tour"); sys.exit(1)
except X.Rechazo as e:
    assert "vuelve a conectar" in str(e)
PY

# ── la lista de pasos y las preguntas ──
python3 "$ROOT/plugin/hermes-seo/hseo_aterrizaje.py" empezar tour >/dev/null
si "paso 3 (cómo se publica): con el servidor MCP conectado, hecho" "jq -e '.pasos[\"3\"].ok' $W/aterrizaje.json"
printf '# Mis preguntas\n1. ¿Cómo puede oírme todo el grupo?\n2) ¿Qué alternativa hay a las radioguías?\n- ¿Hay una app para oír al guía?\n¿Cuánto cuesta alquilar receptores?\nWhat is the best whisper system?\n' > "$T/p.txt"
si "las preguntas para la IA se guardan donde las leen las herramientas" "python3 $ROOT/plugin/hermes-seo/hseo_cli.py preguntas tour < $T/p.txt && grep -q '^5. What is the best whisper system?' $W/preguntas-decision.md && ! grep -q 'Mis preguntas' $W/preguntas-decision.md"
printf 'Usar estas en la prueba, son las de un cliente.\n\n1. ¿Una pregunta larga?\n2. ¿Otra pregunta larga?\n3. ¿La tercera pregunta?\n4. ¿La cuarta pregunta?\n5. ¿La quinta pregunta?\n' > "$T/p2.txt"
si "con una lista numerada, el texto de alrededor no cuenta como pregunta" "python3 $ROOT/plugin/hermes-seo/hseo_cli.py preguntas tour < $T/p2.txt | grep -q '5 preguntas'"
no "menos de 5 preguntas no se guardan" "printf '1. ¿Una?\n' | python3 $ROOT/plugin/hermes-seo/hseo_cli.py preguntas tour"
exit $fail
