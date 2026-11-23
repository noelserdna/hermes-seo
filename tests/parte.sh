#!/usr/bin/env bash
# Parte semanal sin IA: cifras, faltas, lo hecho, puertas, hasta 3 propuestas validadas (una de título como mucho),
# «haz la N» lanza una vez; el cron del lunes existe.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
P="$ROOT/plugin/hermes-seo"; H="python3 $P/hseo_cli.py"
python3 "$P/hseo_clientes.py" alta web web.com --estado repo --nombre "La Web" >/dev/null
python3 "$P/hseo_clientes.py" config web capacidades.publicacion '{"adaptador":"repo-pr","repo":"/tmp/r"}' >/dev/null
python3 "$P/hseo_clientes.py" config web capacidades.busqueda '{"gsc":"sc-domain:web.com"}' >/dev/null 2>&1 || true
si "sin datos el parte sale igual y dice qué falta" "$H parte web --no-guardar | grep -q 'Falta: Search Console'"
python3 - "$HERMES_SEO_HOME/clientes/web" <<'PY'
import json, sys
from datetime import date, timedelta
from pathlib import Path
d = Path(sys.argv[1]) / "datos" / "gsc"; d.mkdir(parents=True)
hoy = date.today()
for i in range(56):
    f = hoy - timedelta(days=58 - i)
    datos = {"totales": {"clics": 3, "impresiones": 300, "ctr": 0.01, "posicion": 9.0},
             "consulta_pagina": [{"query": "que es x", "page": "https://web.com/x", "clics": 0, "impresiones": 30, "ctr": 0, "posicion": 12.0}],
             "pagina": [{"page": "https://web.com/a", "clics": 0, "impresiones": 60, "ctr": 0, "posicion": 5.0},
                        {"page": "https://web.com/b", "clics": 0, "impresiones": 40, "ctr": 0, "posicion": 6.0}]}
    (d / f"{f.isoformat()}.json").write_text(json.dumps(datos))
PY
python3 "$P/hseo_datos.py" actualizar web >/dev/null
si "sin opción no genera nada: dice que aún no hay parte y no crea ficheros" "$H parte web | grep -q 'aún no tiene ningún parte' && [ ! -e $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json ]"
OUT=$($H parte web --enviar)
echo "$OUT" | grep -q "📊 Parte de la semana · La Web" && echo "$OUT" | grep -q "84 clics" && ok "cifras de 28 días" || bad "cifras ($OUT)"
N=$(echo "$OUT" | grep -c '^[0-9]\. ')
[ "$N" -ge 1 ] && [ "$N" -le 3 ] && ok "entre 1 y 3 propuestas" || bad "propuestas ($N)"
[ "$(echo "$OUT" | grep -c 'Mejorar el título')" -le 1 ] && ok "como mucho una de título" || bad "una de título"
si "se guarda ultimo.json" "[ -f $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json ]"
COD=$(jq -r '.propuestas[0].codigo' $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json)
si "consultar el parte no lo regenera: mismos códigos, mismo texto" "$H parte web | grep -q 'Parte de la semana' && [ \"\$(jq -r '.propuestas[0].codigo' $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json)\" = '$COD' ]"
si "el cron dos veces el mismo día: la segunda no rehace ni cambia los códigos" "$H parte web --enviar 2>&1 | grep -q 'ya se envió' && [ \"\$(jq -r '.propuestas[0].codigo' $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json)\" = '$COD' ]"
si "haz la 1: lanza" "$H propuesta web 1 | grep -q '✅ Propuesta 1'"
si "haz la 1 otra vez: ya se lanzó" "$H propuesta web 1 | grep -q 'ya se lanzó'"
si "el siguiente parte ya no la propone (está en marcha)" "! $H parte web --no-guardar | grep -q \"\$(jq -r '.propuestas[0].texto' $HERMES_SEO_HOME/clientes/web/informes/partes/ultimo.json | cut -c1-40)\""
si "antes de descartar, propone llevar «que es x» a la primera página" "$H parte web --no-guardar | grep -q 'que es x'"
mkdir -p "$HERMES_SEO_HOME/clientes/web/encargos/actualizacion-x-1"
echo "{\"id\":\"actualizacion-x-1\",\"pipeline\":\"actualizacion\",\"estado\":\"descartado\",\"creado\":\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\",\"params\":{\"url\":\"https://web.com/x\"},\"etapas\":[]}" > "$HERMES_SEO_HOME/clientes/web/encargos/actualizacion-x-1/encargo.json"
si "descartada por la persona: el parte no la vuelve a proponer" "! $H parte web --no-guardar | grep -q 'que es x'"
si "una propuesta que no existe se rechaza" "! $H propuesta web 9"
si "el plan de crons incluye el parte del lunes a las 10:30" "python3 $P/hseo_crons.py plan web | jq -e 'any(.[]; .nombre == \"parte\" and .horario == \"30 10 * * 1\" and .orden == [\"parte\", \"web\", \"--enviar\"])'"
python3 - "$HERMES_SEO_HOME/clientes/web" <<'PY'
import json, sys, time
from pathlib import Path
open(Path(sys.argv[1]) / "cambios.jsonl", "a").write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ"), "url": "https://web.com/b/"}) + "\n")
PY
si "una página cambiada hace menos de 28 días no se propone" "! $H parte web --no-guardar | grep -q 'web.com/b\|/b (' "
si "decimales con coma" "$H parte web --no-guardar | grep -q 'posición 9,0'"
python3 - "$P" <<'PY' && ok "umbrales: 1 impresión no se propone; una propuesta por página; la consulta objetivo lejos del top 20 sí; web en arranque o con el acceso caído: ninguna de búsquedas" || bad "umbrales del parte"
import importlib.util, sys
from pathlib import Path
P = Path(sys.argv[1]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
PA = m("hseo_parte")
def r(dias=28, **k):
    return {"hay_datos": True, "actual": {"dias": dias}, "marca": {"terminos": ["web"]}, "bajo_ctr": [], "pagina_dos": [], "lejos": [], **k}
q = lambda c, u, i, pos: {"consulta": c, "pagina": f"https://web.com/{u}", "impresiones": i, "clics": 0, "posicion": pos}
ids = lambda rr, **k: [(x["id"], x["orden"].get("params", {}).get("url", "")) for x in PA.propuestas("web", rr, **k) if x["id"] not in ("sin-mapa", "parada")]
assert ids(r(pagina_dos=[q("hire a guide", "g", 1, 9.0)])) == []                                    # una impresión es ruido
assert ids(r(pagina_dos=[q("la web opiniones", "g", 400, 9.0)])) == []                             # consulta de marca
dos = r(pagina_dos=[q("mcp", "blog/que-es-mcp", 1000, 9.7), q("mcp protocolo", "blog/que-es-mcp", 300, 12.0)],
        lejos=[q("que es mcp", "blog/que-es-mcp", 27, 46.2), q("otra cosa", "blog/que-es-mcp", 90, 30.0)])
pr = PA.propuestas("web", dos); mias = [x for x in pr if x["id"] == "pagina-dos"]
assert len(mias) == 1 and "«que es mcp»" in mias[0]["orden"]["params"]["motivo"] and "objetivo" in mias[0]["texto"], pr   # una por página, con su objetivo
assert ids(r(lejos=[q("que es un mcp", "blog/que-es-mcp", 25, 54.6)])) == [("objetivo-lejos", "https://web.com/blog/que-es-mcp")]
assert ids(r(lejos=[q("que es un mcp", "blog/que-es-mcp", 5, 54.6)])) == []                        # pocas impresiones
assert PA._objetivo("mcp que es", "https://web.com/blog/que-es-mcp") and not PA._objetivo("mcp server", "https://web.com/blog/que-es-mcp")
assert ids(r(dias=6, pagina_dos=[q("mcp", "blog/que-es-mcp", 1000, 9.7)])) == []                   # web en arranque
assert ids(r(pagina_dos=[q("mcp", "blog/que-es-mcp", 1000, 9.7)]), sin_gsc=True) == []             # acceso caído: cifras viejas
bajo = lambda pos, imp, esp, cl: {"pagina": "https://web.com/t", "impresiones": imp, "clics": cl, "posicion": pos, "clics_esperados": esp}
assert ids(r(bajo_ctr=[bajo(18.0, 400, 4.0, 0)])) == [] and ids(r(bajo_ctr=[bajo(6.0, 120, 2.0, 0)])) == []   # fuera de la 1.ª página / poca ganancia
assert [i for i, _ in ids(r(bajo_ctr=[bajo(6.6, 995, 30.0, 5)]))] == ["bajo-ctr"]
PY
python3 - "$P" "$HERMES_SEO_HOME/clientes/web" <<'PY' && ok "el parte abre con lo que sigue roto, no propone sobre datos parados y no compara 28 días con menos" || bad "incidencias en el parte"
import importlib.util, json, sys
from pathlib import Path
P, D = Path(sys.argv[1]), Path(sys.argv[2]); sys.path.insert(0, str(P))
def m(n):
    s = importlib.util.spec_from_file_location(n, P / f"{n}.py"); x = importlib.util.module_from_spec(s); sys.modules[n] = x; s.loader.exec_module(x); return x
PA = m("hseo_parte")
(D / "incidencias").mkdir(exist_ok=True)
(D / "incidencias" / "acceso-search-console.json").write_text(json.dumps({"clase": "acceso", "recurso": "search-console", "estado": "avisada",
    "creada": "2026-11-21T05:05:39Z", "texto": "el acceso a Search Console ha caducado", "mano": "reconectar Search Console"}))
parte = PA.generar("web"); t = PA.texto(parte).splitlines()
assert t[1].startswith("🔴 Sin resolver desde el 2026-11-21: el acceso a Search Console ha caducado") and "tu mano" in t[1], t[:3]
assert parte["sin_gsc"] and not [x for x in parte["propuestas"] if x["id"] in ("pagina-dos", "bajo-ctr", "tanda", "objetivo-lejos")]
assert "no propongo sobre cifras viejas" in PA.texto(parte) or parte["propuestas"]
(D / "incidencias" / "acceso-search-console.json").unlink()
parte = PA.generar("web"); parte["cifras"]["anterior"]["dias"] = 21
assert "sin comparación: del periodo anterior solo hay 21 días" in PA.texto(parte) and "%)" not in PA.texto(parte).splitlines()[1]
PY
exit $fail
