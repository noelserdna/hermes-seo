#!/usr/bin/env bash
# Adaptadores de publicación (lo que ejecuta el notario al aprobar «Publicar»): entrega, repo-pr y WordPress, con la
# política «antes de publicar», la pausa y cambios.jsonl. Sin red: repo git local, gh falso y un WordPress falso.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d)
export HERMES_SEO_HOME="$T/home" FALSO_GH="$T/gh" PATH="$ROOT/tests/dobles:$PATH"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
C="python3 $ROOT/plugin/hermes-seo/hseo_clientes.py"
encargo() {  # encargo <web> <id> <publicacion.json>
  local d="$HERMES_SEO_HOME/clientes/$1/encargos/$2"; mkdir -p "$d"
  printf '%s' "$3" > "$d/publicacion.json"
  printf -- '---\ntitulo: Qué es X\nmeta_descripcion: Todo sobre X\n---\n# Qué es X\n\nX es **una cosa** con [enlace](https://x.org).\n\n- uno\n- dos\n' > "$d/borrador.md"
}
py() { python3 - "$ROOT" "$@" <<'PY'
import importlib.util, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_publicacion", Path(sys.argv[1]) / "plugin/hermes-seo/hseo_publicacion.py")
P = importlib.util.module_from_spec(spec); sys.modules["hseo_publicacion"] = P; spec.loader.exec_module(P)
try:
    print(P.publicar(sys.argv[2], sys.argv[3], "Ana (telegram)"))
except P.Rechazo as e:
    print("RECHAZO", e); sys.exit(2)
PY
}

# ── entrega ──
$C alta ajena ajena.com --estado sin-acceso >/dev/null
encargo ajena enc1 '{"tipo":"nuevo","url":"https://ajena.com/que-es-x","contenido":"borrador.md","clase":"articulo","hipotesis":"Entrar en el top 10 de «qué es x» en 8 semanas"}'
R=$(py ajena enc1); [ $? = 0 ] && ok "entrega: publica el paquete" || bad "entrega: $R"
D="$HERMES_SEO_HOME/clientes/ajena/entregas/enc1"
[ -f "$D/LEEME.md" ] && grep -q "Qué es X" "$D/LEEME.md" && grep -q "<strong>una cosa</strong>" "$D/contenido.html" && ok "entrega: LEEME, Markdown y HTML" || bad "entrega: ficheros"
grep -q '"clase": "articulo"' "$HERMES_SEO_HOME/clientes/ajena/cambios.jsonl" && grep -q "top 10" "$HERMES_SEO_HOME/clientes/ajena/cambios.jsonl" && ok "cambios.jsonl con clase e hipótesis" || bad "cambios.jsonl"
encargo ajena enc2 '{"tipo":"cambio-tecnico","cambios":[{"accion":"titulo","url":"https://ajena.com/","antes":"Inicio","despues":"Ajena: qué hacemos"}],"hipotesis":"CTR +1 punto","como_deshacer":"Volver al título anterior"}'
py ajena enc2 >/dev/null && grep -q "Ajena: qué hacemos" "$HERMES_SEO_HOME/clientes/ajena/entregas/enc2/LEEME.md" && ok "entrega: cambio técnico con antes y después" || bad "entrega: cambio técnico"
encargo ajena enc3 '{"tipo":"nuevo"}'
R=$(py ajena enc3); [ $? = 2 ] && ok "sin contenido no se publica" || bad "sin contenido: $R"

# ── repo-pr ──
git init -q --bare "$T/origen.git"; git clone -q "$T/origen.git" "$T/web" 2>/dev/null
git -C "$T/web" -c user.name=t -c user.email=t@t commit -q --allow-empty -m inicio && git -C "$T/web" push -q origin HEAD:main 2>/dev/null
$C alta conrepo conrepo.com --estado repo >/dev/null
$C config conrepo capacidades.publicacion "{\"adaptador\":\"repo-pr\",\"repo\":\"$T/web\",\"contenido_dir\":\"src/content/blog\",\"extension\":\".mdx\",\"frontmatter\":{\"title\":\"{titulo}\",\"description\":\"{meta_descripcion}\",\"pubDate\":\"{fecha}\",\"draft\":\"false\"},\"autor_git\":\"Equipo <equipo@conrepo.com>\"}" >/dev/null
encargo conrepo enc1 '{"tipo":"nuevo","url":"https://conrepo.com/blog/qué-es-x/","contenido":"borrador.md","clase":"articulo","hipotesis":"h"}'
R=$(py conrepo enc1); [ $? = 0 ] && echo "$R" | grep -q "pull/42" && ok "repo-pr: PR abierto" || bad "repo-pr: $R"
git -C "$T/origen.git" rev-parse -q --verify refs/heads/hseo/enc1 >/dev/null && ok "repo-pr: la rama hseo/enc1 está en el remoto" || bad "repo-pr: rama"
F=$(git -C "$T/origen.git" show hseo/enc1:src/content/blog/que-es-x.mdx 2>/dev/null)
echo "$F" | grep -q '^title: "Qué es X"' && echo "$F" | grep -q '^draft: "false"' && echo "$F" | grep -q '# Qué es X' && ok "repo-pr: fichero con su cabecera y el slug sin tildes" || bad "repo-pr: contenido ($F)"
git -C "$T/origen.git" log -1 --format='%an <%ae>' hseo/enc1 | grep -q 'Equipo <equipo@conrepo.com>' && ok "repo-pr: autor de la web" || bad "repo-pr: autor"
grep -q -- "--base main" "$FALSO_GH" && grep -q "Hipótesis: h" "$FALSO_GH" && ok "repo-pr: PR contra main con clase e hipótesis" || bad "repo-pr: gh"
git -C "$T/origen.git" rev-parse -q --verify refs/heads/main >/dev/null && [ "$(git -C "$T/origen.git" rev-parse main)" = "$(git -C "$T/web" rev-parse HEAD)" ] && ok "repo-pr: main no se toca" || bad "repo-pr: main cambió"
mkdir -p "$HERMES_SEO_HOME/clientes/conrepo/extensiones"
printf '#!/usr/bin/env bash\necho "desplegando $1" > %s/desplegado\n' "$T" > "$HERMES_SEO_HOME/clientes/conrepo/extensiones/desplegar.sh"
$C config conrepo capacidades.publicacion.desplegar "desplegar.sh {pr}" >/dev/null
encargo conrepo enc2 '{"tipo":"nuevo","titulo":"Otra","contenido":"borrador.md"}'
py conrepo enc2 | grep -q "despliegue lanzado" && sleep 1 && grep -q "desplegando 42" "$T/desplegado" && ok "repo-pr: lanza el despliegue de la web con el número del PR" || bad "repo-pr: despliegue"
$C config conrepo capacidades.publicacion.desplegar "../../../malo.sh" >/dev/null
encargo conrepo enc3 '{"tipo":"nuevo","titulo":"Tercera","contenido":"borrador.md"}'
R=$(py conrepo enc3); echo "$R" | grep -q "no encuentro el script" && ok "repo-pr: el despliegue solo desde las extensiones de la web" || bad "repo-pr: script fuera ($R)"

$C config conrepo capacidades.publicacion.desplegar "desplegar.sh {pr}" >/dev/null; rm -f "$T/desplegado"; : > "$FALSO_GH"
encargo conrepo enc5 '{"tipo":"nuevo","titulo":"Con PR propio","pr":"https://github.com/ejemplo/web/pull/77"}'
R=$(py conrepo enc5); sleep 1
echo "$R" | grep -q "pull/77 · despliegue lanzado" && grep -q "desplegando 77" "$T/desplegado" && [ ! -s "$FALSO_GH" ] && ok "repo-pr: si la etapa ya abrió el PR, solo se despliega" || bad "repo-pr con PR propio: $R"

# ── política antes de publicar y pausa ──
printf '#!/usr/bin/env bash\necho "la web sirve una copia: hay partido"; exit 1\n' > "$HERMES_SEO_HOME/clientes/conrepo/extensiones/ventana.sh"
$C config conrepo politicas.antes_de_publicar ventana.sh >/dev/null
encargo conrepo enc4 '{"tipo":"nuevo","titulo":"Cuarta","contenido":"borrador.md"}'
R=$(py conrepo enc4); [ $? = 2 ] && echo "$R" | grep -q "hay partido" && ok "antes de publicar: la política del cliente lo impide con su motivo" || bad "antes de publicar: $R"
$C config conrepo politicas.antes_de_publicar "" >/dev/null; $C config conrepo politicas.pausado true >/dev/null
R=$(py conrepo enc4); echo "$R" | grep -q "en pausa" && ok "en pausa no se publica" || bad "pausa: $R"

# ── WordPress (servidor falso) ──
PUERTO=$(python3 -c 'import socket;s=socket.socket();s.bind(("127.0.0.1",0));print(s.getsockname()[1])')
python3 - "$PUERTO" "$T/wp" <<'PY' &
import json, sys
from http.server import BaseHTTPRequestHandler, HTTPServer
log = open(sys.argv[2], "a")
class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _r(self, cuerpo):
        self.send_response(200); self.send_header("Content-Type", "application/json"); self.end_headers()
        self.wfile.write(json.dumps(cuerpo).encode())
    def do_GET(self):
        log.write(f"GET {self.path}\n"); log.flush()
        self._r([{"id": 7}] if "slug=existente" in self.path else [])
    def do_POST(self):
        n = int(self.headers.get("Content-Length") or 0); d = json.loads(self.rfile.read(n) or b"{}")
        log.write(f"POST {self.path} {self.headers.get('Authorization')} {json.dumps(d, ensure_ascii=False)}\n"); log.flush()
        self._r({"id": 9, "link": "https://wp.test/?p=9"})
HTTPServer(("127.0.0.1", int(sys.argv[1])), H).serve_forever()
PY
SRV=$!; disown $SRV 2>/dev/null; trap 'kill $SRV 2>/dev/null; rm -rf "$T"' EXIT; sleep 0.5
$C alta wpweb wp.test --estado wordpress >/dev/null
$C config wpweb capacidades.publicacion "{\"adaptador\":\"wordpress\",\"url_api\":\"https://wp.test/wp-json\"}" >/dev/null
python3 - "$HERMES_SEO_HOME/clientes/wpweb/cliente.json" "$PUERTO" <<'PY'
import json, sys
f = sys.argv[1]; c = json.load(open(f)); c["capacidades"]["publicacion"]["url_api"] = f"http://127.0.0.1:{sys.argv[2]}/wp-json"
json.dump(c, open(f, "w"))
PY
encargo wpweb enc1 '{"tipo":"nuevo","url":"https://wp.test/que-es-x/","contenido":"borrador.md"}'
R=$(py wpweb enc1); echo "$R" | grep -q "Faltan WP_USUARIO" && ok "wordpress: sin claves, error claro" || bad "wordpress sin claves: $R"
printf 'WP_USUARIO=editor\nWP_APP_PASSWORD=abcd efgh\n' > "$HERMES_SEO_HOME/clientes/wpweb/secretos.env"
R=$(py wpweb enc1); echo "$R" | grep -q "publicada: https://wp.test/?p=9" && ok "wordpress: publica la entrada" || bad "wordpress: $R"
grep -q 'POST /wp-json/wp/v2/posts Basic ZWRpdG9yOmFiY2QgZWZnaA==' "$T/wp" && grep -q '"slug": "que-es-x"' "$T/wp" && grep -q '<strong>una cosa</strong>' "$T/wp" && grep -q '"status": "publish"' "$T/wp" && ok "wordpress: contraseña de aplicación, slug y HTML" || bad "wordpress: petición ($(cat $T/wp))"
encargo wpweb enc2 '{"tipo":"actualizacion","url":"https://wp.test/existente/","contenido":"borrador.md"}'
py wpweb enc2 | grep -q "actualizada" && grep -q 'POST /wp-json/wp/v2/posts/7' "$T/wp" && ok "wordpress: actualiza la entrada que ya existe" || bad "wordpress: actualización"
encargo wpweb enc3 '{"tipo":"actualizacion","url":"https://wp.test/no-existe/","contenido":"borrador.md"}'
R=$(py wpweb enc3); echo "$R" | grep -q "No encuentro en WordPress" && ok "wordpress: no inventa una página que no existe" || bad "wordpress: $R"
exit $fail
