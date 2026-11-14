#!/usr/bin/env bash
# De punta a punta sin IA: lanzar un encargo (tarjetas encadenadas en el tablero del cliente), ejecutar sus etapas con
# un ejecutor falso, abrir la puerta al acabar, decidir (persona y Jev), deshacer, firmar y lo que hace el notario
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
si "5 tarjetas encadenadas para la estación" "[ \$(grep -c 'kanban --board web create' $FALSO_LLAMADAS) = 5 ] && [ \$(grep -c -- '--parent' $FALSO_LLAMADAS) = 4 ] && grep -q 'assignee seo-estacion' $FALSO_LLAMADAS"
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
r=$(bash "$ROOT/etapa.sh" web "$EID" preparar | ultima)
GID=$(echo "$r" | jq -r '.puerta // empty')
si "la última etapa abre la puerta de publicar" "[ -n '$GID' ] && $PU ver $GID | jq -e '.tipo == \"publicar\" and .estado == \"abierta\"'"
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
si "rehacer archiva las 4 tarjetas viejas" "[ \$(grep -c 'kanban --board web archive' $FALSO_LLAMADAS) = 4 ]"
si "rehacer crea 4 tarjetas nuevas (redactar → preparar)" "[ \$(grep -c -- '--idempotency-key $EID-.*-r1' $FALSO_LLAMADAS) = 4 ]"
si "el feedback llega al prompt de redactar" "bash $ROOT/etapa.sh web $EID redactar >/dev/null && grep -q . $D/.estado/feedback-redactar.txt"
for e in verificar revisar-lectura; do bash "$ROOT/etapa.sh" web "$EID" "$e" >/dev/null; done
GID2=$(bash "$ROOT/etapa.sh" web "$EID" preparar | tail -1 | jq -r '.puerta // empty')
si "segunda ronda: nueva puerta" "[ -n '$GID2' ] && [ '$GID2' != '$GID' ]"
python3 - "$GID2" <<PY && ok "aprobar sin una publicación válida: error visible, no se pierde la decisión" || bad "publicar sin adaptador"
exec(open("$T/py").read())
g = sys.argv[1]
PU.decidir(g, "acepto", "", "ana", "telegram", "111")
assert rechaza(lambda: PU.firmar(g))
p = PU.leer(g)
assert p["estado"] == "error" and "publicacion.json" in p["error"], p
PY
si "puertas.jsonl registra la firma" "grep -q '\"verbo\": \"cambios\"' $HERMES_SEO_HOME/clientes/web/puertas.jsonl"

# ── pipeline siguiente y descartar ──
R=$($EN lanzar web alta --quien ana); A=$(echo "$R" | jq -r .encargo)
GA=$(bash "$ROOT/etapa.sh" web "$A" alta | tail -1 | jq -r '.puerta // empty')
si "aprobar el alta lanza la línea base" "$PU decidir-local $GA acepto && ls $HERMES_SEO_HOME/clientes/web/encargos | grep -q '^linea-base-'"
R=$($EN lanzar web radar); RD=$(echo "$R" | jq -r .encargo)
GR=$(bash "$ROOT/etapa.sh" web "$RD" radar | tail -1 | jq -r '.puerta // empty')
si "rechazar cierra el encargo como descartado" "$PU decidir-local $GR rechazo 'No interesa' && jq -e '.estado == \"descartado\"' $HERMES_SEO_HOME/clientes/web/encargos/$RD/encargo.json"

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

# ── Jev ──
R=$($EN lanzar web radar); J1=$(echo "$R" | jq -r .encargo)
GJ=$(bash "$ROOT/etapa.sh" web "$J1" radar | tail -1 | jq -r '.puerta // empty')
python3 - "$GJ" <<PY && ok "Jev: modos, umbrales, reservadas, avisos graves, veto al deshacer y firma como Jev" || bad "Jev"
exec(open("$T/py").read())
g = sys.argv[1]
alto = {"choice": "acepto", "p": 0.95, "modelo": "jev-latest"}
p = PU.aplicar_jev(g, alto); assert not p["jev"]["decide"] and p["estado"] == "abierta"       # humano por defecto
PU.poner_modo("consejo", "web"); p = PU.aplicar_jev(g, alto); assert not p["jev"]["decide"]
assert "aprobaría" in PU.describir_jev(p)
PU.poner_modo("piloto", "web"); p = PU.aplicar_jev(g, alto); assert p["jev"]["decide"]       # plan-editorial está en piloto
PU.deshacer(g, "ana"); p = PU.leer(g); assert p["jev_vetado"]
p = PU.aplicar_jev(g, alto); assert not p["jev"]["decide"] and "deshizo" in p["jev"]["motivo"]  # vetado
PY
R=$($EN lanzar web radar); J2=$(echo "$R" | jq -r .encargo)
GJ2=$(bash "$ROOT/etapa.sh" web "$J2" radar | tail -1 | jq -r '.puerta // empty')
GALTA=$(bash "$ROOT/etapa.sh" web "$($EN lanzar web alta | jq -r .encargo)" alta | tail -1 | jq -r '.puerta // empty')
python3 - "$GJ2" "$GALTA" <<PY && ok "Jev en auto: umbral propio, nunca reservadas ni rechazos, el notario lo vuelve a comprobar" || bad "Jev auto"
exec(open("$T/py").read())
g, galta = sys.argv[1], sys.argv[2]
PU.poner_modo("auto", "web")
p = PU.aplicar_jev(g, {"choice": "acepto", "p": 0.75}); assert not p["jev"]["decide"]          # < 0.8
p = PU.leer(g); p.pop("jev"); PU.B.escribir(PU.indice(g), p)
p = PU.aplicar_jev(g, {"choice": "persona", "p": 0.99}); assert not p["jev"]["decide"]
p = PU.leer(g); p.pop("jev"); PU.B.escribir(PU.indice(g), p)
p = PU.aplicar_jev(galta, {"choice": "acepto", "p": 0.99}); assert not p["jev"]["decide"]       # alta: reservada
p = PU.aplicar_jev(g, {"choice": "acepto", "p": 0.85}); assert p["jev"]["decide"]
PU.poner_modo("consejo", "web")                                                                # cambia antes de firmar
assert rechaza(lambda: PU.firmar(g)) and PU.leer(g)["estado"] == "error"
PU.poner_modo("auto", "web")
PU.C.config("web", "jev.permitido", False)
assert PU.modo_jev("web") == "humano"                                                          # el cliente lo prohíbe
PY
python3 - <<PY && ok "umbrales: entre 0.5 y 1; piloto no admite reservadas" || bad "umbrales"
exec(open("$T/py").read())
assert rechaza(lambda: PU.ajustar_jev(umbral=0.3))
assert rechaza(lambda: PU.ajustar_jev(piloto=["alta"]))
assert PU.ajustar_jev(umbral_auto=0.85)["umbral_auto"] == 0.85
PY
exit $fail
