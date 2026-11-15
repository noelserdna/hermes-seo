#!/usr/bin/env bash
# Memoria de la web sin modelo: páginas fijas en sus momentos (configuración, puerta firmada con su corrección,
# publicación, fin de la estrategia), idempotentes, en index y log, y cada etapa recibe lo que le toca.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros" HERMES_SEO_DESHACER_S=0
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta web web.com --nombre "La Web" >/dev/null
W=$HERMES_SEO_HOME/clientes/web/wiki; mkdir -p $W/concepts; printf '# Wiki\n\n## Concepts\n' > $W/index.md; : > $W/log.md
cp "$ROOT/encargado/wiki/SCHEMA.md" $W/SCHEMA.md 2>/dev/null; sed -i.bak '/## Fixed pages/,$d' $W/SCHEMA.md; (cd $W && git init -q && git add -A && git -c user.name=x -c user.email=x@x commit -qm init)
echo "{\"ana\":{\"nombre\":\"Ana\",\"canales\":{\"telegram\":\"111\",\"local\":\"$(id -un)\"},\"clientes\":[\"*\"]}}" > "$HERMES_SEO_HOME/aprobadores.json"
python3 - "$P" <<'PY' && ok "configuración → negocio.md; puerta rechazada con motivo → decisiones y correcciones; idempotente; index, log y git" || bad "momentos"
import importlib.util, subprocess, sys
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
B, C, PU, WK = m("hseo_base"), m("hseo_clientes"), m("hseo_puertas"), m("hseo_wiki")
W = C.carpeta("web") / "wiki"
C.config("web", "negocio.publico", "Desarrolladores hispanohablantes")
assert "Desarrolladores hispanohablantes" in (W / "concepts/negocio.md").read_text()
g = PU.abrir("web", tipo="decision", titulo="📊 X", texto="x")["id"]
PU.decidir_local(g, "rechazo", "Menos tecnicismos en el título")
assert "Menos tecnicismos" in (W / "concepts/correcciones.md").read_text()
assert "rechazo" in (W / "concepts/decisiones.md").read_text()
idx = (W / "index.md").read_text(); assert "[[negocio]]" in idx and "[[correcciones]]" in idx and idx.count("[[decisiones]]") == 1
antes = (W / "log.md").read_text(); WK.regenerar_decisiones("web"); assert (W / "log.md").read_text() == antes   # sin cambios, nada
assert "hermes-seo" in subprocess.run(["git", "-C", str(W), "log", "--oneline"], capture_output=True, text=True).stdout
PY
python3 - "$P" <<'PY' && ok "fin de la estrategia → mapa-tematico.md (su sección); la etapa recibe su memoria en el contexto" || bad "estrategia y lectura"
import importlib.util, sys
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
C, E, WK, ET = m("hseo_clientes"), m("hseo_encargos"), m("hseo_wiki"), m("hseo_etapa")
e = E.lanzar("web", "estrategia")
d = E.carpeta("web", e["id"]); (d / "plan-editorial.md").write_text("# Plan\n\n## Resumen\nx\n\n## Mapa temático: un tema, una página\n- qué es x → /x\n\n## Plan editorial\n- otra cosa\n")
WK.de_salida("web", e["id"], {"pagina": "mapa-tematico", "de": "plan-editorial.md", "seccion": "Mapa temático"})
mt = (C.carpeta("web") / "wiki/concepts/mapa-tematico.md").read_text()
assert "qué es x → /x" in mt and "otra cosa" not in mt, mt
ctx = ET.contexto("web", "redactar"); assert "Memoria que te toca" in ctx and "qué es x → /x" in ctx and "Menos tecnicismos" in ctx, ctx
assert "qué es x" not in ET.contexto("web", "verificar")      # verificar no recibe el mapa
PY
python3 "$P/hseo_cli.py" wiki sembrar web | grep -q "Memoria sembrada" && grep -q "## Fixed pages" $W/SCHEMA.md && ok "sembrar: idempotente y el SCHEMA conoce las páginas fijas" || bad "sembrar"
exit $fail
