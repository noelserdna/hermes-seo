#!/usr/bin/env bash
# De punta a punta sin IA: lanzar un encargo (tarjetas encadenadas en el tablero del cliente), ejecutar sus etapas con
# un ejecutor falso, abrir la puerta al acabar, decidir, deshacer, firmar y lo que hace el notario
# (aprobar, rehacer con cambios, lanzar la pipeline siguiente, descartar).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HERMES_BIN="$ROOT/tests/dobles/hermes" HSEO_EJECUTORES="$ROOT/tests/dobles" HOME="$T/casa"
export FALSO_LLAMADAS="$T/llamadas" FALSO_TABLEROS="$T/tableros" FALSO_EJECUCIONES="$T/ejecuciones" HERMES_SEO_DESHACER_S=0
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
C="python3 $P/hseo_clientes.py"; EN="python3 $P/hseo_encargos.py"; PU="python3 $P/hseo_puertas.py"
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }
ultima() { tail -1; }

$C alta web web.com --estado repo >/dev/null
$C config web capacidades.publicacion '{"adaptador":"repo-pr","repo":"/tmp/r"}' >/dev/null
echo "{\"ana\":{\"nombre\":\"Ana\",\"canales\":{\"telegram\":\"111\",\"local\":\"$(id -un)\"},\"clientes\":[\"*\"]},\"luis\":{\"nombre\":\"Luis\",\"canales\":{\"telegram\":\"222\"},\"clientes\":[\"otra\"]}}" > "$HERMES_SEO_HOME/aprobadores.json"

# ── lanzar ──
no "un artículo sin tema no se lanza" "$EN lanzar web articulo"
no "un parámetro que no existe no se lanza" "$EN lanzar web articulo --param tema=x --param color=rojo"
si "en seco no crea nada" "$EN lanzar web articulo --param tema='Qué es X' --seco && [ ! -d $HERMES_SEO_HOME/clientes/web/encargos ]"
R=$($EN lanzar web articulo --param tema='Qué es X' --quien ana)
EID=$(echo "$R" | jq -r .encargo)
si "lanzar crea el encargo" "[ -f $HERMES_SEO_HOME/clientes/web/encargos/$EID/encargo.json ]"
si "crea el tablero del cliente" "grep -q 'kanban boards create web' $FALSO_LLAMADAS"
si "6 tarjetas encadenadas para la estación" "[ \$(grep -c 'kanban --board web create' $FALSO_LLAMADAS) = 6 ] && [ \$(grep -c -- '--parent' $FALSO_LLAMADAS) = 5 ] && grep -q 'assignee seo-estacion' $FALSO_LLAMADAS"
si "el cuerpo de la tarjeta es «Ejecuta: etapa.sh»" "grep -q 'Ejecuta: bash .*etapa.sh web $EID investigar' $FALSO_LLAMADAS"
si "idempotente por etapa" "grep -q -- '--idempotency-key $EID-redactar' $FALSO_LLAMADAS"
si "el brief lleva lo pedido" "grep -q 'Qué es X' $HERMES_SEO_HOME/clientes/web/encargos/$EID/brief.md"
si "queda en encargos.jsonl como pieza nueva" "grep -q '\"nueva_pieza\": true' $HERMES_SEO_HOME/clientes/web/encargos.jsonl"

# ── etapas ──
D="$HERMES_SEO_HOME/clientes/web/encargos/$EID"
r=$(bash "$ROOT/etapa.sh" web "$EID" investigar | ultima)
si "una etapa sale done" "echo '$r' | jq -e '.outcome == \"done\"'"
si "deja su salida y el contexto del cliente" "[ -f $D/investigacion.md ] && grep -q 'Cliente: web' $D/contexto-cliente.md"
si "el modelo de la etapa llega al ejecutor (investigar: Sonnet por defecto en hermes → sin proveedor, vacío)" "grep -q '^investigar||seo-investigador|investigacion-a-fondo' $FALSO_EJECUCIONES"
r=$(bash "$ROOT/etapa.sh" web "$EID" redactar | ultima)
si "redactar va a Claude con Opus" "grep -q '^redactar|opus|seo-redactor|redactar' $FALSO_EJECUCIONES"
r=$(FALSO_MODO=sinsalida bash "$ROOT/etapa.sh" web "$EID" verificar | ultima)
si "done sin su salida es un fallo" "echo '$r' | jq -e '.outcome == \"failed\" and (.reason | test(\"verificacion.md\"))'"
si "el encargo queda parado" "jq -e '.estado == \"parado\"' $D/encargo.json"
si "etapas.jsonl lo apunta" "[ \$(wc -l < $HERMES_SEO_HOME/clientes/web/etapas.jsonl) = 3 ]"
no "una etapa que no es del encargo" "bash $ROOT/etapa.sh web $EID inventada | tail -1 | jq -e '.outcome == \"done\"'"
for e in verificar revisar-lectura; do bash "$ROOT/etapa.sh" web "$EID" "$e" >/dev/null; done
bash "$ROOT/etapa.sh" web "$EID" preparar >/dev/null
r=$(bash "$ROOT/etapa.sh" web "$EID" comprobar | ultima)
GID=$(echo "$r" | jq -r '.puerta // empty')
si "la última etapa abre la puerta de publicar" "[ -n '$GID' ] && $PU ver $GID | jq -e '.tipo == \"publicar\" and .estado == \"abierta\"'"
si "con una comprobación detrás, la puerta sigue enseñando la publicación (no el informe de la comprobación)" "$PU ver $GID | jq -e '.texto | test(\"comprobacion.md\") and (test(\"Resultado de comprobar\") | not)'"
si "el encargo pasa a «en puerta»" "jq -e '.estado == \"en-puerta\" and .puerta_id == \"$GID\"' $D/encargo.json"
no "no abre dos puertas para el mismo encargo" "$PU abrir web $EID"
$C config web politicas.pausado true >/dev/null
si "en pausa, una etapa espera (scheduled)" "bash $ROOT/etapa.sh web $EID investigar | tail -1 | jq -e '.outcome == \"scheduled\"'"
$C config web politicas.pausado false >/dev/null

# ── decidir, deshacer, firmar ──
cat > "$T/py" <<'PY'
import importlib.util, sys, os
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_puertas", Path(os.environ["P"]) / "hseo_puertas.py")
PU = importlib.util.module_from_spec(spec); sys.modules["hseo_puertas"] = PU; spec.loader.exec_module(PU)
def rechaza(f):
    try: f(); return False
    except PU.Rechazo: return True
PY
export P
python3 - "$GID" <<PY && ok "decidir: autorización por canal y cliente, motivo obligatorio, deshacer" || bad "decidir"
exec(open("$T/py").read())
g = sys.argv[1]
assert rechaza(lambda: PU.decidir(g, "acepto", "", "ana", "telegram", "999"))       # otra identidad
assert rechaza(lambda: PU.decidir(g, "acepto", "", "luis", "telegram", "222"))      # no es de este cliente
assert rechaza(lambda: PU.decidir(g, "cambios", "", "ana", "telegram", "111"))      # cambios sin motivo
assert rechaza(lambda: PU.decidir(g, "borrar", "", "ana", "telegram", "111"))       # opción que no existe
PU.decidir(g, "cambios", "Más ejemplos", "ana", "telegram", "111")
assert rechaza(lambda: PU.decidir(g, "acepto", "", "ana", "telegram", "111"))       # ya decidida
assert rechaza(lambda: PU.deshacer(g, "luis"))                                      # solo quien decidió
PU.deshacer(g, "ana")
assert PU.leer(g)["estado"] == "abierta"
PY
python3 - "$GID" <<PY && ok "cambios: el notario rehace desde redactar con lo pedido" || bad "cambios"
exec(open("$T/py").read())
import json
g = sys.argv[1]
PU.decidir(g, "cambios", "Más ejemplos, menos jerga", "ana", "telegram", "111")
p = PU.firmar(g)
assert p["estado"] == "firmada" and "redactar" in p["resultado"], p
assert "Ana (telegram)" == p["firma"], p["firma"]
d = Path(os.environ["HERMES_SEO_HOME"]) / "clientes/web/encargos"
enc = json.load(open(next(d.glob("*/encargo.json"))))
assert enc["estado"] == "en-curso" and enc["rondas"] == 1 and "puerta_id" not in enc
assert "Más ejemplos" in (next(d.glob("*")) / ".estado/feedback-redactar.txt").read_text()
PY
si "rehacer archiva las 5 tarjetas viejas" "[ \$(grep -c 'kanban --board web archive' $FALSO_LLAMADAS) = 5 ]"
si "rehacer crea 5 tarjetas nuevas (redactar → comprobar)" "[ \$(grep -c -- '--idempotency-key $EID-.*-r1' $FALSO_LLAMADAS) = 5 ]"
si "el feedback llega al prompt de redactar" "bash $ROOT/etapa.sh web $EID redactar >/dev/null && grep -q . $D/.estado/feedback-redactar.txt"
si "al rehacer, una etapa que no cambia su salida (lo pedido ya estaba) no es un fallo" "FALSO_MODO=sinsalida bash $ROOT/etapa.sh web $EID redactar | tail -1 | jq -e '.outcome == \"done\" and (.resumen | test(\"lo pedido ya estaba\"))'"
for e in verificar revisar-lectura; do bash "$ROOT/etapa.sh" web "$EID" "$e" >/dev/null; done
bash "$ROOT/etapa.sh" web "$EID" preparar >/dev/null
GID2=$(bash "$ROOT/etapa.sh" web "$EID" comprobar | tail -1 | jq -r '.puerta // empty')
si "segunda ronda: nueva puerta" "[ -n '$GID2' ] && [ '$GID2' != '$GID' ]"
python3 - "$GID2" <<PY && ok "sin una publicación válida (aviso grave) no se aprueba; forzada, el notario da error visible" || bad "publicar sin adaptador"
exec(open("$T/py").read())
g = sys.argv[1]
assert PU.graves(PU.leer(g)) and rechaza(lambda: PU.decidir(g, "acepto", "", "ana", "telegram", "111"))
PU.decidir(g, "acepto", "", "ana", "local", PU.getpass.getuser(), {"forzado": "prueba"})
assert rechaza(lambda: PU.firmar(g))
p = PU.leer(g)
assert p["estado"] == "error" and "publicacion.json" in p["error"], p
PY
si "puertas.jsonl registra la firma" "grep -q '\"verbo\": \"cambios\"' $HERMES_SEO_HOME/clientes/web/puertas.jsonl"

# ── pipeline siguiente y descartar ──
R=$($EN lanzar web alta --quien ana); A=$(echo "$R" | jq -r .encargo)
GA=$(bash "$ROOT/etapa.sh" web "$A" alta | tail -1 | jq -r '.puerta // empty')
si "el alta es un informe (la línea base la lanza el aterrizaje): no abre puerta" "[ -z '$GA' ] && jq -e '.estado == \"hecho\" and .informe' $HERMES_SEO_HOME/clientes/web/encargos/$A/encargo.json"
# un informe (al_aprobar: nada) no abre puerta: queda hecho y sale en el parte
R=$($EN lanzar web radar); RI=$(echo "$R" | jq -r .encargo)
GI=$(bash "$ROOT/etapa.sh" web "$RI" radar | tail -1 | jq -r '.puerta // empty')
si "un informe no abre puerta y queda hecho" "[ -z '$GI' ] && jq -e '.estado == \"hecho\" and .informe' $HERMES_SEO_HOME/clientes/web/encargos/$RI/encargo.json"
si "y se puede volver a lanzar (no cuenta como duplicado)" "$EN lanzar web radar | jq -e '.duplicado | not'"
no "el mismo trabajo en marcha no se lanza dos veces" "$EN lanzar web radar | jq -e '.duplicado | not'"
# una pipeline cuya puerta ejecuta algo, para probar las decisiones
mkdir -p "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines"
cat > "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines/plan.json" <<'J'
{"id":"plan","nombre":"Plan","parametros":{"n":"vuelta"},"etapas":[{"id":"radar","titulo":"Plan {n}","perfil":"seo-analista","skill":"radar","salida":"radar.md"}],
 "puerta":{"tipo":"plan-editorial","al_aprobar":"script:nada.sh"}}
J
printf '#!/usr/bin/env bash\ntrue\n' > "$HERMES_SEO_HOME/clientes/web/extensiones/nada.sh"
R=$($EN lanzar web plan --param n=1 --excepcion); RD=$(echo "$R" | jq -r .encargo)
GR=$(bash "$ROOT/etapa.sh" web "$RD" radar | tail -1 | jq -r '.puerta // empty')
si "rechazar cierra el encargo como descartado" "$PU decidir-local $GR rechazo 'No interesa' && jq -e '.estado == \"descartado\"' $HERMES_SEO_HOME/clientes/web/encargos/$RD/encargo.json"

mkdir -p "$HERMES_SEO_HOME/clientes/web/extensiones/skills/radar-propia" "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines"; echo "# propia" > "$HERMES_SEO_HOME/clientes/web/extensiones/skills/radar-propia/SKILL.md"
cat > "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines/conpropia.json" <<'J'
{"id":"conpropia","nombre":"Con skill propia","etapas":[{"id":"redactar","titulo":"x","perfil":"seo-redactor","skill":"radar-propia","ejecutor":"claude","salida":"x.md"}]}
J
CP=$($EN lanzar web conpropia | jq -r .encargo); bash "$ROOT/etapa.sh" web "$CP" redactar >/dev/null
si "Claude recibe la ruta de la skill propia de la web" "grep -q 'extensiones/skills/radar-propia/SKILL.md' $HERMES_SEO_HOME/clientes/web/encargos/$CP/.estado/ultimo-prompt.txt"

# ── continuación con herencia y script de la web ──
mkdir -p "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines"
cat > "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines/primera.json" <<'J'
{"id":"primera","nombre":"Primera","parametros":{"tema":"t"},"nueva_pieza":true,"etapas":[{"id":"investigar","titulo":"Uno: {tema}","perfil":"seo-investigador","skill":"radar","salida":"uno.md"}],
 "puerta":{"tipo":"difusion","al_aprobar":"pipeline:segunda"}}
J
cat > "$HERMES_SEO_HOME/clientes/web/extensiones/pipelines/segunda.json" <<'J'
{"id":"segunda","nombre":"Segunda","parametros":{"tema":"t"},"etapas":[{"id":"redactar","titulo":"Dos: {tema}","perfil":"seo-redactor","skill":"radar","salida":"dos.md"}],
 "puerta":{"tipo":"difusion","al_aprobar":"script:publicar.sh {encargo} extra"}}
J
printf '#!/usr/bin/env bash\necho "$1 $2 $HSEO_FIRMA" > "$HERMES_SEO_HOME/script-hecho"\n' > "$HERMES_SEO_HOME/clientes/web/extensiones/publicar.sh"
$C config web politicas.tope_semanal 0 >/dev/null; $C config web politicas.congelado_hasta "" >/dev/null
P1=$($EN lanzar web primera --param tema=capturas | jq -r .encargo)
G1=$(bash "$ROOT/etapa.sh" web "$P1" investigar | tail -1 | jq -r '.puerta // empty')
$C config web politicas.congelado_hasta 2099-01-01 >/dev/null
$PU decidir-local $G1 acepto > $T/dl.out 2>&1; cat $T/dl.out >&2
si "aprobar lanza la continuación aunque haya congelación (ya pasó las políticas)" "grep -q Firmada $T/dl.out"
P2=$(ls $HERMES_SEO_HOME/clientes/web/encargos | grep '^segunda-' | head -1)
si "la continuación hereda parámetros y salidas" "[ -n '$P2' ] && jq -e '.params.tema == \"capturas\" and .origen == \"$P1\"' $HERMES_SEO_HOME/clientes/web/encargos/$P2/encargo.json && [ -f $HERMES_SEO_HOME/clientes/web/encargos/$P2/uno.md ]"
si "y no cuenta como pieza nueva otra vez" "tail -1 $HERMES_SEO_HOME/clientes/web/encargos.jsonl | jq -e '.nueva_pieza == false'"
G2=$(bash "$ROOT/etapa.sh" web "$P2" redactar | tail -1 | jq -r '.puerta // empty')
si "la etapa ve lo heredado como previo" "grep -q 'uno.md (from $P1)' $HERMES_SEO_HOME/clientes/web/encargos/$P2/.estado/ultimo-prompt.txt"
si "script: lanza el script de la web con el encargo y la firma" "$PU decidir-local $G2 acepto && sleep 1 && grep -q '^$P2 extra' $HERMES_SEO_HOME/script-hecho"
$C config web politicas.congelado_hasta "" >/dev/null

# ── aviso grave: no se aprueba (solo cambios o descartar); --forzar desde local, con motivo y registrado ──
R=$($EN lanzar web plan --param n=2 --excepcion); J1=$(echo "$R" | jq -r .encargo)
GJ=$(bash "$ROOT/etapa.sh" web "$J1" radar | tail -1 | jq -r '.puerta // empty')
python3 - "$GJ" <<PY && ok "con un aviso grave no se aprueba, y la opción de aprobar no se ofrece" || bad "aviso grave"
exec(open("$T/py").read())
g = sys.argv[1]
p = PU.leer(g); p["revision"] = {"avisos": [{"grave": True, "codigo": "x", "texto": "x"}], "graves": 1}; PU.B.escribir(PU.indice(g), p)
assert rechaza(lambda: PU.decidir(g, "acepto", "", "ana", "telegram", "111"))
assert [o["verbo"] for o in PU.opciones_vigentes(PU.leer(g))] == ["cambios", "rechazo"]
assert PU.leer(g)["estado"] == "abierta"
PY
no "decidir-local sin --forzar tampoco aprueba" "$PU decidir-local $GJ acepto"
si "con --forzar y motivo sí, y queda escrito" "$PU decidir-local $GJ acepto --forzar 'lo reviso yo' && grep -q 'lo reviso yo' $HERMES_SEO_HOME/clientes/web/puertas.jsonl"
si "Jev ya no existe en las puertas" "! grep -q -i jev $ROOT/plugin/hermes-seo/hseo_puertas.py"
# ── la verificación pide cambios: una vuelta automática a redactar; la segunda vez sigue a la puerta con aviso grave ──
RV=$($EN lanzar web articulo --param tema='Vuelta' --excepcion); EV=$(echo "$RV" | jq -r .encargo); DV=$HERMES_SEO_HOME/clientes/web/encargos/$EV
for e in investigar redactar; do bash "$ROOT/etapa.sh" web "$EV" "$e" >/dev/null; done
OUT=$(FALSO_MODO=cambios bash "$ROOT/etapa.sh" web "$EV" verificar | tail -1)
si "CAMBIOS en la verificación: la tarjeta no sigue y el encargo queda en-vuelta" "echo '$OUT' | jq -e '.outcome == \"failed\" and .vuelta == \"redactar\"' && jq -e '.estado == \"en-vuelta\" and .vuelta_pendiente.desde == \"redactar\"' $DV/encargo.json && [ -f $DV/verificacion-1.md ]"
si "etapas.jsonl lo apunta como «cambios», no como fallo" "tail -1 $HERMES_SEO_HOME/clientes/web/etapas.jsonl | jq -e '.resultado == \"cambios\"'"
si "hseo vueltas la lanza: tarjetas nuevas desde redactar" "python3 $P/hseo_cli.py vueltas | grep -q '$EV' && jq -e '.estado == \"en-curso\" and (.vuelta_pendiente | not)' $DV/encargo.json && grep -q -- '--idempotency-key $EV-redactar-r1' $FALSO_LLAMADAS"
si "el feedback de la verificación va aparte y llega al redactor" "[ -f $DV/.estado/feedback-verificacion-redactar.txt ] && [ ! -f $DV/.estado/feedback-redactar.txt ] && bash $ROOT/etapa.sh web $EV redactar >/dev/null && grep -q 'fact-check' $DV/.estado/ultimo-prompt.txt && grep -q 'corregir la cifra' $DV/.estado/ultimo-prompt.txt"
OUT2=$(FALSO_MODO=cambios bash "$ROOT/etapa.sh" web "$EV" verificar | tail -1)
si "segunda vez CAMBIOS: ya no vuelve, sigue" "echo '$OUT2' | jq -e '.outcome == \"done\"' && jq -e '.estado == \"en-curso\" and .vueltas_verificacion == 1' $DV/encargo.json"
for e in revisar-lectura; do bash "$ROOT/etapa.sh" web "$EV" "$e" >/dev/null; done
bash "$ROOT/etapa.sh" web "$EV" preparar >/dev/null
OUT3=$(FALSO_MODO=cambios bash "$ROOT/etapa.sh" web "$EV" comprobar | tail -1)
si "la comprobación final ve cambios sin aplicar: vuelve a preparar (una vez, con su propio contador)" "echo '$OUT3' | jq -e '.outcome == \"failed\" and .vuelta == \"preparar\"' && jq -e '.vueltas_comprobar == 1 and .vuelta_pendiente.desde == \"preparar\"' $DV/encargo.json"
python3 $P/hseo_cli.py vueltas >/dev/null; bash "$ROOT/etapa.sh" web "$EV" preparar >/dev/null
GV=$(FALSO_MODO=cambios bash "$ROOT/etapa.sh" web "$EV" comprobar | tail -1 | jq -r '.puerta // empty')
si "y llega a la puerta con el aviso grave (no se puede aprobar)" "[ -n '$GV' ] && $PU ver $GV | jq -e '.revision.graves > 0'"
RA=$($EN lanzar web articulo --param tema='Aplicados' --excepcion); EA=$(echo "$RA" | jq -r .encargo)
for e in investigar redactar; do bash "$ROOT/etapa.sh" web "$EA" "$e" >/dev/null; done
FALSO_MODO=cambios bash "$ROOT/etapa.sh" web "$EA" verificar >/dev/null; python3 $P/hseo_cli.py vueltas >/dev/null
for e in redactar; do bash "$ROOT/etapa.sh" web "$EA" "$e" >/dev/null; done
FALSO_MODO=cambios bash "$ROOT/etapa.sh" web "$EA" verificar >/dev/null
for e in revisar-lectura preparar; do bash "$ROOT/etapa.sh" web "$EA" "$e" >/dev/null; done
echo '{"tipo":"nuevo","titulo":"Un título de prueba suficientemente largo","meta_descripcion":"Meta","contenido":"borrador.md"}' > $HERMES_SEO_HOME/clientes/web/encargos/$EA/publicacion.json
GA=$(bash "$ROOT/etapa.sh" web "$EA" comprobar | tail -1 | jq -r '.puerta // empty')
si "verificación con CAMBIOS pero comprobado que están aplicados: sin aviso grave por la verificación" "[ -n '$GA' ] && $PU ver $GA | jq -e '([.revision.avisos[] | select(.codigo == \"verificacion-cambios\")] | length == 0) and any(.revision.avisos[]; .codigo == \"verificacion-aplicados\")'"
no "una pipeline con si_cambios a una etapa posterior no valida" "python3 -c \"import importlib.util,sys;s=importlib.util.spec_from_file_location('p','$P/hseo_pipelines.py');m=importlib.util.module_from_spec(s);sys.modules['p']=m;s.loader.exec_module(m);sys.exit(1 if m.validar({'id':'x','nombre':'x','etapas':[{'id':'a','perfil':'seo-redactor','skill':'redactar','si_cambios':'b'},{'id':'b','perfil':'seo-redactor','skill':'redactar'}]}) else 0)\""
exit $fail
