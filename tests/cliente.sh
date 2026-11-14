#!/usr/bin/env bash
# Clientes: alta, validación, capacidades por estado de la web y cambios de configuración con historial.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
C="python3 $ROOT/plugin/hermes-seo/hseo_clientes.py"
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }

si "alta de una web nueva" "$C alta nueva-web nueva-web.com"
si "crea su carpeta con wiki, datos y secretos 600" \
   "[ -d $HERMES_SEO_HOME/clientes/nueva-web/wiki ] && [ -d $HERMES_SEO_HOME/clientes/nueva-web/datos ] && [ \$(python3 -c \"import os,sys;print(oct(os.stat(sys.argv[1]).st_mode & 0o777)[2:])\" $HERMES_SEO_HOME/clientes/nueva-web/secretos.env) = 600 ]"
no "no repite un alta" "$C alta nueva-web otra.com"
no "rechaza un slug con mayúsculas" "$C alta Mala otra.com"
no "rechaza un nombre reservado" "$C alta cartera otra.com"
si "limpia https:// y la barra del dominio" "$C alta limpia https://Limpia.es/ && $C ver limpia | grep -q '\"dominio\": \"limpia.es\"'"
no "rechaza un dominio sin TLD" "$C alta malo malo"

si "una web sin acceso publica por entrega" "$C alta ajena ajena.com --estado sin-acceso && $C capacidades ajena | grep -q 'publicacion:entrega'"
no "una web wordpress no admite repo-pr" "$C alta wpweb wp.com --estado wordpress && $C config wpweb capacidades.publicacion.adaptador repo-pr"
no "wordpress pide la url de la API" "$C config wpweb capacidades.publicacion.adaptador wordpress"
si "wordpress con url de API" "$C config wpweb capacidades.publicacion '{\"adaptador\":\"wordpress\",\"url_api\":\"https://wp.com/wp-json\"}'"
si "repo-pr con su repo da la capacidad repo" \
   "$C alta conrepo conrepo.com --estado repo && $C config conrepo capacidades.publicacion '{\"adaptador\":\"repo-pr\",\"repo\":\"/tmp/r\"}' && $C capacidades conrepo | grep -qw repo"
si "gsc y bing como capacidades" \
   "$C config conrepo capacidades.busqueda '{\"gsc\":\"sc-domain:conrepo.com\",\"bing\":\"https://conrepo.com/\"}' && $C capacidades conrepo | grep -qw gsc && $C capacidades conrepo | grep -qw bing"
no "rechaza una zona horaria inventada" "$C config conrepo zona_horaria Marte/Olimpo"
no "rechaza un mercado mal escrito" "$C config conrepo mercados '[{\"pais\":\"es\",\"bing\":\"es\"}]'"
si "acepta varios mercados" "$C config conrepo mercados '[{\"pais\":\"ES\",\"bing\":\"es-ES\"},{\"pais\":\"MX\",\"bing\":\"es-MX\"}]'"
no "no deja cambiar el slug" "$C config conrepo slug otro"
si "un cambio de config queda en el historial" "grep -q '\"clave\": \"mercados\"' $HERMES_SEO_HOME/clientes/conrepo/config.jsonl"
si "un cambio rechazado no se escribe" "$C ver conrepo | grep -q 'Europe/Madrid'"
si "Jev se puede prohibir por cliente" "$C config conrepo jev.permitido false && ! $C capacidades conrepo | grep -qw jev"
si "listar enseña todos" "[ \$($C listar --json | python3 -c 'import json,sys;print(len(json.load(sys.stdin)))') = 5 ]"
si "validar un cliente sano" "$C validar conrepo"

python3 - "$ROOT" <<'PY' && ok "secretos: los del cliente mandan sobre los globales y no hay comentarios" || bad "secretos"
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_clientes", Path(sys.argv[1]) / "plugin/hermes-seo/hseo_clientes.py")
C = importlib.util.module_from_spec(spec); sys.modules["hseo_clientes"] = C; spec.loader.exec_module(C)
h = Path(os.environ["HERMES_SEO_HOME"])
(h / "secretos.env").write_text("BRAVE=global\nOPENAI='abc'\n")
(h / "clientes/conrepo/secretos.env").write_text("# nota\nBRAVE=propio\n")
s = C.secretos("conrepo")
assert s == {"BRAVE": "propio", "OPENAI": "abc"}, s
PY
exit $fail
