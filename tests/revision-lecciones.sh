#!/usr/bin/env bash
# Revisión mecánica en las puertas (avisos y graves que vetan a Jev) y lecciones entre webs (proponer con evidencia,
# reglas generales, confirmar, usar en otras webs, revisar tras 3 usos, wiki global).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
python3 "$P/hseo_clientes.py" alta tienda tienda.com >/dev/null
for w in otra1 otra2 otra3; do python3 "$P/hseo_clientes.py" alta $w $w.com >/dev/null; done
python3 - "$P" <<'PY' && ok "revisión: publicar (verificación, título, meta, longitud, hipótesis, canibalización) y técnico" || bad "revisión"
import importlib.util, json, sys, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_revision", Path(sys.argv[1]) / "hseo_revision.py")
R = importlib.util.module_from_spec(spec); sys.modules["hseo_revision"] = R; spec.loader.exec_module(R)
C, E = R.C, R.E
d = C.carpeta("tienda") / "encargos" / "art-uno"; d.mkdir(parents=True)
E.guardar("tienda", {"id": "art-uno", "pipeline": "articulo", "etapas": [], "saltadas": [{"id": "competencia", "falta": ["competidores"]}]})
codigos = lambda r: {a["codigo"]: a["grave"] for a in r["avisos"]}
r = R.revisar("tienda", "art-uno", "publicar"); assert codigos(r) == {"sin-publicacion": True, "etapas-saltadas": False}, r
(d / "publicacion.json").write_text(json.dumps({"tipo": "nuevo", "contenido": "borrador.md", "url": "https://tienda.com/a",
                                                "busqueda_principal": "zapatillas trail"}))
(d / "borrador.md").write_text("---\ntitulo: Corto\n---\n# Uno\n# Dos\n" + "palabra " * 50)
(d / "verificacion.md").write_text("...\nVEREDICTO: CAMBIOS\n")
(d / "lectura.md").write_text("...\n")
c = codigos(R.revisar("tienda", "art-uno", "publicar"))
assert c["verificacion-cambios"] and c["contenido-corto"] and not c["titulo-largo"] and not c["sin-meta"], c
assert not c["lectura-sin-veredicto"] and not c["sin-hipotesis"] and not c["varios-h1"], c
(d / "verificacion.md").write_text("VEREDICTO: APROBADO\n"); (d / "lectura.md").write_text("VEREDICTO: APROBADO\n")
(d / "borrador.md").write_text("---\ntitulo: Zapatillas de trail: cómo elegir las tuyas\nmeta_descripcion: Guía\n---\n# Uno\n" + "palabra " * 300)
pub = json.loads((d / "publicacion.json").read_text()); pub["hipotesis"] = "top 10 en 8 semanas"; (d / "publicacion.json").write_text(json.dumps(pub))
(C.carpeta("tienda") / "cambios.jsonl").write_text(json.dumps({"url": "https://tienda.com/b", "hipotesis": "zapatillas trail"}) + "\n")
r = R.revisar("tienda", "art-uno", "publicar"); c = codigos(r)
assert r["graves"] == 0 and set(c) == {"canibalizacion", "etapas-saltadas"}, r
pub = {"tipo": "cambio-tecnico", "cambios": [{"accion": "redireccion", "antes": "/a/", "despues": "/a"}, {"accion": "noindex", "url": "/b"}]}
(d / "publicacion.json").write_text(json.dumps(pub))
c = codigos(R.revisar("tienda", "art-uno", "cambio-tecnico"))
assert c["redireccion-bucle"] and c["quita-paginas"] and c["sin-hipotesis"] and not c["sin-deshacer"], c
PY
python3 - "$P" <<'PY' && ok "lecciones: evidencia, regla general, confirmar, otras webs, revisar a las 3, wiki global" || bad "lecciones"
import importlib.util, json, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_lecciones", Path(sys.argv[1]) / "hseo_lecciones.py")
L = importlib.util.module_from_spec(spec); sys.modules["hseo_lecciones"] = L; spec.loader.exec_module(L)
C = L.C
def rechaza(f):
    try: f(); return False
    except L.Rechazo: return True
regla = "Antes de redirigir una página con tráfico, comprobar sus enlaces entrantes"
assert rechaza(lambda: L.proponer("tienda", "analizar-cambio", regla, ["no-existe"]))           # evidencia falsa
(C.carpeta("tienda") / "puertas.jsonl").write_text(json.dumps({"puerta": "gabcdef1234"}) + "\n")
assert rechaza(lambda: L.proponer("tienda", "analizar-cambio", "En tienda.com no redirigir", ["gabcdef1234"]))   # nombra la web
assert rechaza(lambda: L.proponer("tienda", "analizar-cambio", "Mira https://x.com antes de nada, siempre", ["gabcdef1234"]))
assert rechaza(lambda: L.proponer("tienda", "analizar-cambio", "corta", ["gabcdef1234"]))
l = L.proponer("tienda", "analizar-cambio", regla, ["gabcdef1234"])
assert rechaza(lambda: L.proponer("tienda", "analizar-cambio", regla, ["gabcdef1234"]))          # repetida
assert L.para_cliente("otra1", "analizar-cambio") == []                                          # sin confirmar no se usa
L.decidir(l["id"], "confirmar", "ana")
assert L.para_cliente("tienda", "analizar-cambio") == []                                         # no en su propia web
assert L.para_cliente("otra1", "radar") == []                                                    # solo en su etapa
assert L.para_cliente("otra1", "analizar-cambio") == [regla]
L.para_cliente("otra2", "analizar-cambio"); L.para_cliente("otra3", "analizar-cambio")
assert next(x for x in L.todas() if x["id"] == l["id"])["estado"] == "revisar"
assert L.para_cliente("tienda", None, anotar=False) == []
L.decidir(l["id"], "mantener", "ana")
x = next(x for x in L.todas() if x["id"] == l["id"]); assert x["estado"] == "confirmada" and x["usos"] == []
assert regla in (L.B.home() / "wiki/concepts/lecciones.md").read_text()
PY
python3 "$P/hseo_cli.py" leccion tienda radar "Medir la demanda antes de proponer una pieza nueva" gabcdef1234 >/dev/null && ok "hseo leccion la propone" || bad "hseo leccion"
printf '%s' '{"tool_name":"terminal","tool_input":{"command":"hseo leccion tienda radar \"Regla general de prueba larga\" gabc"}}' | python3 -I "$ROOT/encargado/guardia.py" tienda "$ROOT" >/dev/null && ok "el encargado propone lecciones sin aprobación" || bad "guardia leccion"
printf '%s' '{"tool_name":"terminal","tool_input":{"command":"hseo leccion otra1 radar \"Regla general de prueba larga\" gabc"}}' | python3 -I "$ROOT/encargado/guardia.py" tienda "$ROOT" >/dev/null 2>&1 && bad "guardia: lección de otra web" || ok "pero solo de su web"
exit $fail
