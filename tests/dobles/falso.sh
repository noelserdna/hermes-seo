#!/usr/bin/env bash
# Ejecutor falso: escribe la salida que le pide el prompt («Write your result to: X») y responde según FALSO_MODO.
DIR=$1; NOMBRE=$2; PROMPT=$3; MODELO=${4:-}; PERFIL=${5:-}; SKILL=${6:-}
echo "$NOMBRE|$MODELO|$PERFIL|$SKILL" >> "${FALSO_EJECUCIONES:-/dev/null}"
mkdir -p "$DIR/.estado"; printf "%s" "$PROMPT" > "$DIR/.estado/ultimo-prompt.txt"
SALIDA=$(printf '%s' "$PROMPT" | sed -nE 's/^Write your result to: (.*)$/\1/p')
case "${FALSO_MODO:-ok}" in
  ok) printf 'Resultado de %s\nVEREDICTO: APROBADO\n' "$NOMBRE" > "$DIR/$SALIDA"
      jq -nc --arg r "hecho $NOMBRE" '{outcome:"done", reason:"ok", resumen:$r, cost_usd:0.01, minutes:0}' ;;
  cambios) printf 'Resultado de %s\n1. Cambio obligatorio: corregir la cifra\nVEREDICTO: CAMBIOS\n' "$NOMBRE" > "$DIR/$SALIDA"
      jq -nc --arg r "hecho $NOMBRE" '{outcome:"done", reason:"ok", resumen:$r, cost_usd:0.01, minutes:0}' ;;
  cambios) printf 'Resultado de %s\n1. Cambio obligatorio: corregir la cifra\nVEREDICTO: CAMBIOS\n' "$NOMBRE" > "$DIR/$SALIDA"
      jq -nc --arg r "hecho $NOMBRE" '{outcome:"done", reason:"ok", resumen:$r, cost_usd:0.01, minutes:0}' ;;
  sinsalida) jq -nc '{outcome:"done", reason:"ok"}' ;;
  falla) jq -nc '{outcome:"failed", reason:"algo falló"}' ;;
esac
