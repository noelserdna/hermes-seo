#!/usr/bin/env bash
# Manda el latido al Worker (cron cada 5 min). Antes intenta UNA reparación sin modelo: si el gateway de Hermes no está
# activo, lo reinicia; el Worker solo avisa si sigue caído. Configuración: ~/.config/hermes-seo/latido.env
# (HSEO_LATIDO_URL, HSEO_LATIDO_SECRETO; opcional HSEO_LATIDO_SERVICIO, por defecto hermes-gateway).
set -uo pipefail
CONF=${HSEO_LATIDO_CONF:-$HOME/.config/hermes-seo/latido.env}
[ -f "$CONF" ] || { echo "Falta $CONF" >&2; exit 2; }
set -a; . "$CONF"; set +a
SERV=${HSEO_LATIDO_SERVICIO:-hermes-gateway}
estado=$(systemctl is-active "$SERV" 2>/dev/null || true); reiniciado=false
if [ "$estado" != active ] && [ "$estado" != activating ]; then
  echo "$(date -u +%FT%TZ) $SERV «$estado»: lo reinicio" >&2
  sudo -n systemctl restart "$SERV" 2>/dev/null || true
  sleep 20; estado=$(systemctl is-active "$SERV" 2>/dev/null || true); reiniciado=true
fi
disco=$(df --output=pcent / | tail -1 | tr -dc 0-9)
curl -sS --max-time 20 -X POST -H "Authorization: Bearer $HSEO_LATIDO_SECRETO" -H "Content-Type: application/json" \
  -d "{\"gateway\":\"${estado:-desconocido}\",\"disco\":${disco:-0},\"reiniciado\":$reiniciado}" "$HSEO_LATIDO_URL/latido" >/dev/null
