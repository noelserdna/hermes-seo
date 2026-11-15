#!/usr/bin/env bash
# Worker del correo (con KV y envío falsos)
command -v node >/dev/null || { echo "ok   (sin node: se salta)"; exit 0; }
[ -d "$(dirname "$0")/../correo/node_modules/postal-mime" ] || (cd "$(dirname "$0")/../correo" \&\& npm install --silent >/dev/null 2>\&1)
exec node "$(dirname "$0")/correo.mjs"
