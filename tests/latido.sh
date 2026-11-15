#!/usr/bin/env bash
# Worker del latido (lógica de avisos, con KV y Telegram falsos)
command -v node >/dev/null || { echo "ok   (sin node: se salta)"; exit 0; }
exec node "$(dirname "$0")/latido.mjs"
