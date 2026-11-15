#!/usr/bin/env bash
# Vuelve a una instalación anterior de hermes-seo sin tocar datos: reapunta «actual», recopia el plugin al perfil principal
# y a cada encargado, y reinicia el gateway. Con --config <tar> restaura además cron/jobs.json y config.yaml de los perfiles
# desde una copia hecha antes de instalar.
#
#   bash volver.sh                    a la instalación anterior (instalacion.json → anterior)
#   bash volver.sh <carpeta>          a esa carpeta de ~/.hermes/hermes-seo (p. ej. 0.1.0-ae0601e)
#   bash volver.sh … --config <tar>   y restaura cron/jobs.json y config.yaml de los perfiles desde el tar
#   bash volver.sh … --sin-reinicio   no reinicia el gateway (pruebas)
set -euo pipefail
HH="$HOME/.hermes"; HSEO="${HERMES_SEO_HOME:-$HH/hermes-seo}"; HERMES="${HERMES_BIN:-hermes}"
DESTINO=""; TAR=""; REINICIO=true
while [ $# -gt 0 ]; do case $1 in
  --config) TAR=$2; shift 2 ;; --sin-reinicio) REINICIO=false; shift ;;
  -h|--help) sed -n '2,10p' "$0"; exit 0 ;; *) DESTINO=$1; shift ;; esac; done
if [ -z "$DESTINO" ]; then DESTINO=$(jq -r '.anterior // ""' "$HSEO/instalacion.json" 2>/dev/null); fi
[ -n "$DESTINO" ] || { echo "No sé a qué versión volver: pasa la carpeta (ls $HSEO)" >&2; exit 2; }
case $DESTINO in /*) ;; *) DESTINO="$HSEO/$DESTINO" ;; esac
[ -f "$DESTINO/plugin/hermes-seo/plugin.yaml" ] || { echo "$DESTINO no es una instalación de hermes-seo" >&2; exit 2; }
ACTUAL=$(readlink "$HSEO/actual" 2>/dev/null || true)
ln -sfn "$DESTINO" "$HSEO/actual"
for PD in "$HH" "$HH"/profiles/seo-p-*; do
  [ -d "$PD/plugins/hermes-seo" ] || [ "$PD" = "$HH" ] || continue
  mkdir -p "$PD/plugins"; rm -rf "$PD/plugins/hermes-seo"; cp -R "$DESTINO/plugin/hermes-seo" "$PD/plugins/hermes-seo"
done
ln -sfn "$HSEO/actual/hseo" "$HOME/.local/bin/hseo"
jq --arg c "$DESTINO" --arg a "$ACTUAL" '.carpeta = $c | .anterior = $a' "$HSEO/instalacion.json" > "$HSEO/instalacion.json.tmp" \
  && mv "$HSEO/instalacion.json.tmp" "$HSEO/instalacion.json"
if [ -n "$TAR" ]; then
  (cd "$HOME" && tar xzf "$TAR" --wildcards '.hermes/profiles/*/cron/jobs.json' '.hermes/profiles/*/config.yaml' \
     '.hermes/config.yaml' 2>/dev/null) || echo "AVISO: no pude restaurar todo desde $TAR"
  echo "Restaurados cron/jobs.json y config.yaml desde $TAR"
fi
echo "hermes-seo vuelve a $DESTINO (antes: ${ACTUAL:-?})"
if $REINICIO; then
  setsid bash -c 'sleep 3; sudo -n systemctl restart hermes-gateway hermes-dashboard' >/dev/null 2>&1 < /dev/null &
  echo "Reiniciando el gateway en 3 s"
fi
