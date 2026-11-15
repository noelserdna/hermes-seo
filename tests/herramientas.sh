#!/usr/bin/env bash
# Herramientas de datos (herramientas/*): cada una exige --cliente, lee cliente.json, sale con 3 si falta su clave,
# no imprime la clave y deja su salida en clientes/<slug>/datos/. Sin red: un servidor HTTP local hace de Bing,
# Brave, OpenAI, Cloudflare, el MCP de Search Console y las webs (propia y competencia).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d)
SRV=""
trap '[ -n "$SRV" ] && kill $SRV 2>/dev/null; rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HSEO_SIN_PAUSAS=1
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
C="python3 $ROOT/plugin/hermes-seo/hseo_clientes.py"
HT="$ROOT/herramientas"
LOG="$T/peticiones.log"
corre() { out=$("$@" 2>&1); rc=$?; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }

# ---------- servidor falso ----------
cat > "$T/falso.py" <<'PY'
import json, sys, urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
T = Path(sys.argv[1])
CLAVES = {"bing": "clave-bing-secreta", "brave": "clave-brave-secreta", "openai": "clave-openai-secreta",
          "cf": "clave-cf-secreta", "mcp": "token-gsc-secreto"}

class Falso(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def anotar(self, extra=""):
        with open(T / "peticiones.log", "a") as f:
            f.write(f"{self.command} {urllib.parse.unquote_plus(self.path)} {extra}\n")

    def enviar(self, codigo, cuerpo=b"", tipo="text/html; charset=utf-8", cab=None):
        if isinstance(cuerpo, (dict, list)):
            cuerpo, tipo = json.dumps(cuerpo).encode(), "application/json"
        elif isinstance(cuerpo, str):
            cuerpo = cuerpo.encode()
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        for k, v in (cab or {}).items():
            self.send_header(k, v)
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def base(self):
        return f"http://127.0.0.1:{self.server.server_address[1]}"

    def pagina(self, titulo, enlaces):
        a = "".join(f'<a href="{e}">x</a>' for e in enlaces)
        return (f"<html><head><title>{titulo}</title><meta name='description' content='{'d' * 100}'>"
                f"<link rel='canonical' href='{self.base()}{self.path}'></head><body><h1>{titulo}</h1>{a}</body></html>")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        u = urllib.parse.urlparse(self.path)
        q = dict(urllib.parse.parse_qsl(u.query))
        b = self.base()
        if u.path.startswith("/bing/"):
            self.anotar()
            if q.get("apikey") != CLAVES["bing"]:
                return self.enviar(401, {"error": "clave"})
            if u.path.endswith("GetRelatedKeywords"):
                return self.enviar(200, {"d": [{"Query": "Curso Prueba", "Impressions": 7}]})
            if u.path.endswith("GetLinkCounts"):
                return self.enviar(200, {"d": {"Links": [{"Url": "https://prueba-web.com/a/"}], "TotalPages": 1}})
            if u.path.endswith("GetUrlLinks"):
                return self.enviar(200, {"d": {"Details": [{"Url": "https://otra.com/x", "AnchorText": "ancla"}], "TotalPages": 1}})
        if u.path == "/brave":
            self.anotar()
            if self.headers.get("X-Subscription-Token") != CLAVES["brave"]:
                return self.enviar(401, {"error": "clave"})
            res = [{"url": "https://otra.com/1", "title": "otra"}, {"url": "https://www.prueba-web.com/a/", "title": "nuestra"}]
            return self.enviar(200, {"web": {"results": res}})
        rutas = {
            "/robots.txt": ("text/plain", f"User-agent: *\nSitemap: {b}/sitemap-index.xml\n"),
            "/sitemap-index.xml": ("application/xml", f"<sitemapindex><sitemap><loc>{b}/sitemap-0.xml</loc></sitemap></sitemapindex>"),
            "/sitemap-0.xml": ("application/xml", f"<urlset><url><loc>{b}/</loc></url><url><loc>{b}/a/</loc></url>"
                                                  f"<url><loc>{b}/b/</loc></url></urlset>"),
            "/": (None, self.pagina("Portada", ["/a/", "/privado/x", "/roto"])),
            "/a/": (None, self.pagina("Página A", ["/b/"])),
            "/b/": (None, self.pagina("Página B", ["/"])),
        }
        if u.path in rutas:
            tipo, cuerpo = rutas[u.path]
            return self.enviar(200, cuerpo, tipo or "text/html; charset=utf-8")
        if u.path.startswith("/privado/"):
            return self.enviar(302, "", cab={"Location": "/login"})
        return self.enviar(404, "no")

    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0)
        cuerpo = self.rfile.read(n).decode()
        self.anotar(cuerpo)
        auth = self.headers.get("Authorization", "")
        if self.path == "/openai-sinsaldo/responses":
            return self.enviar(429, {"error": {"code": "insufficient_quota", "message": "You exceeded your current quota"}})
        if self.path == "/openai-ritmo/responses":
            Falso.ritmo = getattr(Falso, "ritmo", 0) + 1
            if Falso.ritmo == 1:
                self.send_response(429); self.send_header("Retry-After", "0"); self.send_header("Content-Type", "application/json")
                self.end_headers(); self.wfile.write(b'{"error": {"code": "rate_limit_exceeded"}}'); return
            self.path = "/openai/responses"
        if self.path == "/openai/responses":
            if auth != f"Bearer {CLAVES['openai']}":
                return self.enviar(401, {"error": "clave"})
            return self.enviar(200, {"output": [
                {"type": "web_search_call", "action": {"query": "buscada"}},
                {"type": "message", "content": [{"text": "Respuesta de prueba",
                                                 "annotations": [{"type": "url_citation", "url": "https://prueba-web.com/a/"}]}]}]})
        if self.path == "/cf/graphql":
            if auth != f"Bearer {CLAVES['cf']}":
                return self.enviar(401, {"error": "clave"})
            return self.enviar(200, {"data": {"viewer": {"zones": [{"httpRequestsAdaptiveGroups": [
                {"count": 5, "dimensions": {"userAgent": "Mozilla/5.0 GPTBot/1.0", "clientRequestPath": "/a/"}}]}]}}})
        if self.path == "/mcp":
            if auth != f"Bearer {CLAVES['mcp']}":
                return self.enviar(401, {"error": "token"})
            m = json.loads(cuerpo)
            if "id" not in m:
                return self.enviar(202, "")
            if m["method"] == "initialize":
                return self.enviar(200, {"jsonrpc": "2.0", "id": m["id"], "result": {}}, cab={"Mcp-Session-Id": "s1"})
            a = m["params"]["arguments"]
            if "fechaInicio" not in a:
                r = {"structuredContent": {"periodo": {"fin": "2026-01-05"}}}
            else:
                r = {"structuredContent": {"totales": {"clicks": 1},
                                           "filas": [{"claves": {"query": "q"}, "actual": {"clicks": 1}}]}}
            # una respuesta en SSE para cubrir los dos formatos de Streamable HTTP
            sse = "event: message\ndata: " + json.dumps({"jsonrpc": "2.0", "id": m["id"], "result": r}) + "\n\n"
            return self.enviar(200, sse, "text/event-stream")
        return self.enviar(404, "no")

s = ThreadingHTTPServer(("127.0.0.1", 0), Falso)
(T / "puerto.tmp").write_text(str(s.server_address[1]))
(T / "puerto.tmp").rename(T / "puerto")
s.serve_forever()
PY
python3 "$T/falso.py" "$T" & SRV=$!; disown $SRV 2>/dev/null
for _ in $(seq 50); do [ -f "$T/puerto" ] && break; sleep 0.1; done
P=$(cat "$T/puerto" 2>/dev/null) || { bad "arranca el servidor falso"; exit 1; }
B="http://127.0.0.1:$P"
export HSEO_URL_BING="$B/bing" HSEO_URL_BRAVE="$B/brave" HSEO_URL_OPENAI="$B/openai" HSEO_URL_CF="$B/cf"

# ---------- cliente de prueba ----------
D="$HERMES_SEO_HOME/clientes/prueba"
si "alta del cliente de prueba" "$C alta prueba prueba-web.com"
si "configura mercados, búsqueda, analítica, competidores y rutas privadas" "
  $C config prueba mercados '[{\"pais\":\"MX\",\"bing\":\"es-MX\"},{\"pais\":\"CO\",\"bing\":\"es-ES\"}]' &&
  $C config prueba capacidades.busqueda '{\"gsc\":\"sc-domain:prueba-web.com\",\"bing\":\"https://prueba-web.com/\",\"gsc_mcp\":\"$B/mcp\",\"gsc_perfil\":\"perfil-prueba\"}' &&
  $C config prueba capacidades.analitica '{\"adaptador\":\"cloudflare\",\"zona\":\"0123456789abcdef0123456789abcdef\"}' &&
  $C config prueba competidores '[\"$B /b/\"]' &&
  $C config prueba auditoria.rutas_privadas '[\"/privado/\"]'"
printf '1. ¿Qué curso de prueba recomiendas?\n2. ¿Dónde aprendo pruebas?\n' > "$D/preguntas-decision.md"

# ---------- todas exigen --cliente ----------
for h in auditoria-web demanda-bing enlaces-bing sitemaps-competencia brave-busca chatgpt-busca guardar-gsc bots-ia; do
  si "$h es ejecutable" "[ -x $HT/$h ]"
  corre "$HT/$h"
  if [ $rc -ne 0 ] && echo "$out" | grep -q -- '--cliente'; then ok "$h exige --cliente"; else bad "$h exige --cliente"; fi
  extra=""; [ "$h" = demanda-bing ] && extra=x
  corre "$HT/$h" --cliente no-existe $extra
  if [ $rc -eq 2 ] && echo "$out" | grep -q 'No conozco el cliente'; then ok "$h rechaza un cliente desconocido"; else bad "$h rechaza un cliente desconocido ($rc)"; fi
done

# ---------- sin claves: código 3 ----------
for h in "demanda-bing curso" enlaces-bing brave-busca chatgpt-busca bots-ia; do
  corre $HT/$h --cliente prueba
  if [ $rc -eq 3 ] && echo "$out" | grep -q 'falta'; then ok "${h%% *} sale con 3 si falta su clave"; else bad "${h%% *} sale con 3 si falta su clave ($rc: $out)"; fi
done

cat >> "$D/secretos.env" <<'ENV'
BING_WEBMASTER_API_KEY=clave-bing-secreta
BRAVE_SEARCH_API_KEY=clave-brave-secreta
OPENAI_API_KEY='clave-openai-secreta'
CLOUDFLARE_ANALYTICS_TOKEN="clave-cf-secreta"
ENV
sin_clave() { ! echo "$out" | grep -q -e 'clave-.*-secreta' -e 'token-gsc-secreto'; }
HOY=$(date +%F)

# ---------- demanda-bing ----------
corre "$HT/demanda-bing" --cliente prueba "curso prueba"
if [ $rc -eq 0 ] && echo "$out" | grep -q 'curso prueba | 14 | 7 | 7'; then ok "demanda-bing suma los mercados del cliente"; else bad "demanda-bing ($rc: $out)"; fi
sin_clave && ok "demanda-bing no imprime la clave" || bad "demanda-bing imprime la clave"
si "demanda-bing usa los mercados de cliente.json (mx/es-MX y co/es-ES)" \
   "grep -q 'country=mx&language=es-MX' $LOG && grep -q 'country=co&language=es-ES' $LOG && ! grep -q 'country=ar' $LOG"
si "demanda-bing deja su salida en datos/demanda/" "grep -q 'curso prueba' $D/datos/demanda/$HOY.md"
! grep -q 'clave-bing-secreta' "$D/datos/demanda/$HOY.md" && ok "demanda-bing no guarda la clave" || bad "demanda-bing guarda la clave"

# ---------- enlaces-bing ----------
corre "$HT/enlaces-bing" --cliente prueba
if [ $rc -eq 0 ] && echo "$out" | grep -q '1 enlaces desde 1 dominios' && echo "$out" | grep -q 'Primera foto'; then ok "enlaces-bing hace la primera foto"; else bad "enlaces-bing ($rc: $out)"; fi
sin_clave && ok "enlaces-bing no imprime la clave" || bad "enlaces-bing imprime la clave"
si "enlaces-bing usa el sitio de Bing del cliente" "grep -q 'GetLinkCounts.*siteUrl=https://prueba-web.com/' $LOG"
si "enlaces-bing deja su foto en datos/enlaces/" "grep -q 'otra.com' $D/datos/enlaces/$HOY.json"
corre "$HT/enlaces-bing" --cliente prueba
echo "$out" | grep -q 'Nuevos desde la foto anterior: 0' && ok "enlaces-bing compara con la foto anterior" || bad "enlaces-bing compara ($out)"

# ---------- brave-busca ----------
corre "$HT/brave-busca" --cliente prueba
if [ $rc -eq 0 ] && echo "$out" | tail -1 | grep -q '^BRAVE_OK 2 páginas indexadas, salimos en 2 de 2'; then ok "brave-busca mide el dominio del cliente"; else bad "brave-busca ($rc: $out)"; fi
sin_clave && ok "brave-busca no imprime la clave" || bad "brave-busca imprime la clave"
si "brave-busca usa site:<dominio>, el país del primer mercado y el idioma" \
   "grep -q 'q=site:prueba-web.com&count=20&offset=0&country=MX&search_lang=es' $LOG"
si "brave-busca deja su salida en datos/ia/" \
   "python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); assert d[\"preguntas\"][0][\"puesto\"]==2' $D/datos/ia/brave-$HOY.json"
corre "$HT/brave-busca" --cliente prueba --preguntas "$T/no-hay.md"
[ $rc -eq 2 ] && ok "brave-busca avisa si no hay preguntas" || bad "brave-busca sin preguntas ($rc)"

# ---------- chatgpt-busca ----------
corre "$HT/chatgpt-busca" --cliente prueba --repeticiones 1
if [ $rc -eq 0 ] && echo "$out" | tail -1 | grep -q '^CHATGPT_OK 2 respuestas de 2'; then ok "chatgpt-busca hace las preguntas del cliente"; else bad "chatgpt-busca ($rc: $out)"; fi
sin_clave && ok "chatgpt-busca no imprime la clave" || bad "chatgpt-busca imprime la clave"
si "chatgpt-busca usa el país del primer mercado" "grep -q '\"country\": \"MX\"' $LOG"
si "chatgpt-busca deja su salida en datos/ia/" "grep -q 'Respuesta de prueba' $D/datos/ia/chatgpt-$HOY.json"
HSEO_URL_OPENAI="$B/openai-sinsaldo" corre "$HT/chatgpt-busca" --cliente prueba "$T/sinsaldo.json" --repeticiones 1 --pausa 0
[ $rc -eq 3 ] && echo "$out" | tail -1 | grep -q 'CHATGPT_ERROR sin saldo' && [ "$(grep -c 'openai-sinsaldo' $LOG)" = 1 ] && ok "chatgpt-busca sin saldo: para en la primera llamada (código 3)" || bad "chatgpt-busca sin saldo ($rc: $out)"
HSEO_URL_OPENAI="$B/openai-ritmo" corre "$HT/chatgpt-busca" --cliente prueba "$T/ritmo.json" --repeticiones 1 --pausa 0
[ $rc -eq 0 ] && ok "chatgpt-busca con 429 de ritmo: espera (Retry-After) y sigue" || bad "chatgpt-busca ritmo ($rc: $out)"
python3 -c "import json,sys;f=sys.argv[1];d=json.load(open(f));d['filas'][1]={'n':2,'pregunta':'x','repeticion':1,'error':'antes'};json.dump(d,open(f,'w'))" "$T/ritmo.json"
ANTES=$(grep -c '/openai' $LOG)
corre "$HT/chatgpt-busca" --cliente prueba "$T/ritmo.json" --repeticiones 1 --pausa 0 --reanudar
[ $rc -eq 0 ] && [ "$(( $(grep -c '/openai' $LOG) - ANTES ))" = 1 ] && ok "chatgpt-busca --reanudar: solo pregunta lo que falló" || bad "chatgpt-busca reanudar ($rc)"
corre "$HT/chatgpt-busca" --cliente prueba "$T/otra/salida.json" --repeticiones 1
[ $rc -eq 0 ] && [ -f "$T/otra/salida.json" ] && ok "chatgpt-busca admite otra salida" || bad "chatgpt-busca otra salida"

# ---------- bots-ia ----------
corre "$HT/bots-ia" --cliente prueba --dias 2
if [ $rc -eq 0 ] && echo "$out" | grep -q '| GPTBot | OpenAI | entrenamiento | 10 | /a/ (10) |'; then ok "bots-ia suma los bots de la zona"; else bad "bots-ia ($rc: $out)"; fi
sin_clave && ok "bots-ia no imprime la clave" || bad "bots-ia imprime la clave"
si "bots-ia consulta la zona del cliente" "grep zoneTag $LOG | grep -q 0123456789abcdef0123456789abcdef"
si "bots-ia deja su salida en datos/bots/" "grep -q GPTBot $D/datos/bots/$HOY.md"
$C config prueba capacidades.analitica.adaptador ninguna >/dev/null 2>&1
corre "$HT/bots-ia" --cliente prueba
[ $rc -eq 2 ] && echo "$out" | grep -q 'no mide con Cloudflare' && ok "bots-ia exige el adaptador cloudflare" || bad "bots-ia sin cloudflare ($rc)"

# ---------- guardar-gsc ----------
mkdir -p "$T/bin" "$T/casa"
printf '#!/bin/sh\nexit 0\n' > "$T/bin/hermes"; chmod +x "$T/bin/hermes"
GSC() { HSEO_GSC_ESPERA=0 HOME="$T/casa" PATH="$T/bin:$PATH" "$HT/guardar-gsc" "$@"; }
corre GSC --cliente prueba --desde 2026-01-03
if [ $rc -eq 3 ] && echo "$out" | grep -q 'GSC_ERROR no hay token'; then ok "guardar-gsc sale con 3 si falta el token"; else bad "guardar-gsc sin token ($rc: $out)"; fi
TOK="$T/casa/.hermes/profiles/perfil-prueba/mcp-tokens"; mkdir -p "$TOK"
echo '{"access_token":"token-gsc-secreto","expires_at":0}' > "$TOK/seo.json"
corre GSC --cliente prueba --desde 2026-01-03
if [ $rc -eq 3 ] && echo "$out" | grep -q 'ha caducado'; then ok "guardar-gsc sale con 3 si el token ha caducado"; else bad "guardar-gsc caducado ($rc: $out)"; fi
echo '{"access_token":"token-gsc-secreto","expires_at":99999999999}' > "$TOK/seo.json"
corre GSC --cliente prueba --desde 2026-01-03
if [ $rc -eq 0 ] && echo "$out" | tail -1 | grep -q '^GSC_OK 3 días nuevos (hasta 2026-01-05)'; then ok "guardar-gsc guarda los días desde --desde"; else bad "guardar-gsc ($rc: $out)"; fi
sin_clave && ok "guardar-gsc no imprime el token" || bad "guardar-gsc imprime el token"
si "guardar-gsc usa la propiedad del cliente" "grep -q 'sc-domain:prueba-web.com' $LOG && grep -q '\"sitio\": \"sc-domain:prueba-web.com\"' $D/datos/gsc/2026-01-04.json"
si "guardar-gsc deja un archivo por día en datos/gsc/" "[ -f $D/datos/gsc/2026-01-03.json ] && [ -f $D/datos/gsc/2026-01-05.json ] && [ ! -f $D/datos/gsc/2026-01-02.json ]"
corre GSC --cliente prueba
echo "$out" | tail -1 | grep -q '^GSC_OK 0 días nuevos' && ok "guardar-gsc sin --desde sigue desde lo guardado" || bad "guardar-gsc sin --desde ($out)"
$C config prueba capacidades.busqueda.gsc_mcp '""' >/dev/null 2>&1
corre GSC --cliente prueba
[ $rc -eq 2 ] && echo "$out" | grep -q 'gsc_mcp' && ok "guardar-gsc pide la URL del MCP" || bad "guardar-gsc sin MCP ($rc: $out)"
HSEO_GSC_MCP="$B/mcp" corre GSC --cliente prueba --desde 2026-01-05
[ $rc -eq 0 ] && ok "guardar-gsc acepta HSEO_GSC_MCP" || bad "guardar-gsc con HSEO_GSC_MCP ($rc: $out)"

# ---------- auditoria-web ----------
corre "$HT/auditoria-web" --cliente prueba --sitio "$B"
if [ $rc -eq 0 ] && echo "$out" | grep -q '3 URL en el sitemap' && echo "$out" | grep -q "$B/roto → 404"; then ok "auditoria-web lee el sitemap de robots.txt y encuentra el enlace roto"; else bad "auditoria-web ($rc: $out)"; fi
echo "$out" | grep -q 'privado' && bad "auditoria-web respeta auditoria.rutas_privadas" || ok "auditoria-web respeta auditoria.rutas_privadas"
si "auditoria-web deja su informe en datos/auditoria/" "grep -q 'Auditoría técnica' $D/datos/auditoria/$HOY.md"
$C config prueba auditoria.rutas_privadas '[]' >/dev/null 2>&1
corre "$HT/auditoria-web" --cliente prueba --sitio "$B" --sitemap "$B/sitemap-0.xml" --salida "$T/aud.md"
echo "$out" | grep -q "$B/privado/x → 302" && [ -f "$T/aud.md" ] && ok "auditoria-web sin rutas privadas avisa del 302, con --sitemap y --salida" || bad "auditoria-web --sitemap ($out)"
echo "$out" | grep -qi 'desarrollomcp' && bad "auditoria-web no menciona otra web" || ok "auditoria-web no menciona otra web"

# ---------- sitemaps-competencia ----------
corre "$HT/sitemaps-competencia" --cliente prueba
if [ $rc -eq 0 ] && echo "$out" | grep -q 'primera foto (1 URL)'; then ok "sitemaps-competencia hace la primera foto con el filtro"; else bad "sitemaps-competencia ($rc: $out)"; fi
FOTO="$D/datos/competencia/127.0.0.1_$P.txt"
si "sitemaps-competencia guarda la foto en datos/competencia/" "grep -q '/b/' $FOTO"
: > "$FOTO"
corre "$HT/sitemaps-competencia" --cliente prueba
echo "$out" | grep -q '1 páginas nuevas' && ok "sitemaps-competencia avisa de las páginas nuevas" || bad "sitemaps-competencia nuevas ($out)"
$C config prueba competidores '[]' >/dev/null 2>&1
corre "$HT/sitemaps-competencia" --cliente prueba
[ $rc -eq 2 ] && ok "sitemaps-competencia avisa si no hay competidores" || bad "sitemaps-competencia sin competidores ($rc)"

# ---------- generales ----------
si "ninguna herramienta lleva un dominio, ruta o perfil fijos de otra web" \
   "! grep -rIniE --exclude-dir=__pycache__ 'desarrollomcp|/home/opc|\\.config/desarrollomcp|6cc5768e' $HT"
si "todas usan el User-Agent de hermes-seo" "grep -q 'hermes-seo/0.1 (+https://github.com/noelserdna/hermes-seo)' $HT/_comun.py"
si "ninguna usa sintaxis de Python 3.10+ (compilan con ast de 3.9)" "python3 - $HT <<'PY'
import ast, sys
from pathlib import Path
for p in Path(sys.argv[1]).iterdir():
    if p.is_file() and (p.suffix == '.py' or p.read_text().startswith('#!/usr/bin/python3')):
        ast.parse(p.read_text(), feature_version=(3, 9))
PY"
exit $fail
