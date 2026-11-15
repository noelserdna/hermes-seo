#!/usr/bin/env bash
# Disco: lo primero que se ve (estado, panel, vigía) y worktrees que no se acumulan (14-11: el VPS llegó al 88 %
# con un worktree de ~1 GB por encargo esperando en su puerta).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HOME="$T/casa"; mkdir -p "$HOME"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
P="$ROOT/plugin/hermes-seo"
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
no() { if eval "$2" >/dev/null 2>&1; then bad "$1"; else ok "$1"; fi; }
git config --global user.name prueba >/dev/null 2>&1; git config --global user.email p@x >/dev/null 2>&1
git config --global init.defaultBranch main >/dev/null 2>&1

python3 "$P/hseo_clientes.py" alta web web.com --estado repo >/dev/null

# repo con remoto local y un worktree por encargo
git init -q --bare "$T/remoto.git"
git init -q "$T/repo"; (cd "$T/repo" && echo a > a && git add a && git commit -qm a && git remote add origin "$T/remoto.git" && git push -q origin main)
python3 "$P/hseo_clientes.py" config web capacidades.publicacion \
  "{\"adaptador\":\"repo-pr\",\"repo\":\"$T/repo\",\"worktrees\":\"$T/wt\",\"regenerables\":[\"node_modules\"]}" >/dev/null
no "regenerables con rutas se rechaza" \
  "python3 $P/hseo_clientes.py config web capacidades.publicacion '{\"adaptador\":\"repo-pr\",\"repo\":\"$T/repo\",\"regenerables\":[\"../x\"]}'"

python3 - "$P" "$T" <<'PY' && ok "aligerar borra node_modules y conserva lo demás" || bad "aligerar"
import importlib.util, subprocess, sys
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("hseo_publicacion", P / "hseo_publicacion.py")
PUB = importlib.util.module_from_spec(spec); sys.modules["hseo_publicacion"] = PUB; spec.loader.exec_module(PUB)
subprocess.run(["git", "-C", str(T / "repo"), "worktree", "add", "-q", "-b", "hermes/e1", str(T / "wt" / "e1")], check=True)
(T / "wt" / "e1" / "node_modules" / "x").mkdir(parents=True); (T / "wt" / "e1" / "node_modules" / "x" / "f").write_text("1")
assert PUB.aligerar("web", "e1") == ["node_modules"]
assert not (T / "wt" / "e1" / "node_modules").exists() and (T / "wt" / "e1" / "a").exists()
assert PUB.aligerar("web", "no-existe") == []
PY

python3 - "$P" "$T" <<'PY' && ok "limpiar: no quita con commits sin subir ni con cambios; sí cuando está en el remoto" || bad "limpiar worktree"
import importlib.util, subprocess, sys
from pathlib import Path
P, T = Path(sys.argv[1]), Path(sys.argv[2])
spec = importlib.util.spec_from_file_location("hseo_publicacion", P / "hseo_publicacion.py")
PUB = importlib.util.module_from_spec(spec); sys.modules["hseo_publicacion"] = PUB; spec.loader.exec_module(PUB)
wt = T / "wt" / "e1"
g = lambda *a: subprocess.run(["git", "-C", str(wt), *a], check=True, capture_output=True)
(wt / "b").write_text("b"); g("add", "b"); g("commit", "-qm", "b")
r = PUB.limpiar_worktree("web", "e1"); assert "no están en el remoto" in r and wt.exists(), r
g("push", "-q", "origin", "hermes/e1")
(wt / "a").write_text("cambiado")
r = PUB.limpiar_worktree("web", "e1"); assert "sin guardar" in r and wt.exists(), r
g("checkout", "-q", "--", "a")
r = PUB.limpiar_worktree("web", "e1"); assert r.startswith("quitado") and not wt.exists(), r
assert PUB.limpiar_worktree("web", "e1") == ""
PY

python3 - "$P" <<'PY' && ok "disco: línea con % y GB, aviso según umbral" || bad "disco"
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_base", Path(sys.argv[1]) / "hseo_base.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
d = B.disco()
assert len(d) == 1 and 0 <= d[0]["usado_pct"] <= 100, d       # home, repo y worktrees en el mismo disco: una entrada
assert B.disco_linea().startswith(("💾 Disco: ", "⚠️ Disco: ")) and "GB libres" in B.disco_linea()
os.environ["HSEO_AVISO_DISCO"] = "0"; assert B.disco()[0]["aviso"] and B.disco_linea().startswith("⚠️")
os.environ["HSEO_AVISO_DISCO"] = "101"; assert not B.disco()[0]["aviso"]
PY

si "estado empieza por el disco" "python3 $P/hseo_cli.py estado | head -1 | grep -q 'Disco: .* % usado'"
si "el vigía avisa con el disco por encima del umbral" "HSEO_AVISO_DISCO=0 python3 $P/hseo_encargado.py vigia web | grep -q '^DISCO CASI LLENO | .* | más del'"
no "y no avisa por debajo" "HSEO_AVISO_DISCO=101 python3 $P/hseo_encargado.py vigia web | grep -q DISCO"
echo '{"ts": "2020-01-01T00:00:00Z", "ok": true}' > "$HERMES_SEO_HOME/copia.json"
si "el vigía avisa si la copia lleva más de 2 días sin hacerse" "HSEO_AVISO_DISCO=101 python3 $P/hseo_encargado.py vigia web | grep -q '^COPIA SIN HACER'"
echo '{"ts": "2099-01-01T00:00:00Z", "ok": false, "motivo": "no se pudo subir"}' > "$HERMES_SEO_HOME/copia.json"
si "y si la última copia falló" "HSEO_AVISO_DISCO=101 python3 $P/hseo_encargado.py vigia web | grep -q '^COPIA FALLIDA | r2 | no se pudo subir'"
rm -f "$HERMES_SEO_HOME/copia.json"
no "sin copia configurada, nada" "HSEO_AVISO_DISCO=101 python3 $P/hseo_encargado.py vigia web | grep -q COPIA"
mkdir -p "$T/bin" "$T/run"; printf '#!/bin/sh\nexit 0\n' > "$T/bin/systemd-run"; chmod +x "$T/bin/systemd-run"
python3 - "$P" "$T" <<'PY' && ok "desacoplar: con systemd-run, en su propio scope; sin él o con HSEO_SIN_SCOPE, tal cual" || bad "desacoplar"
import importlib.util, os, sys
from pathlib import Path
spec = importlib.util.spec_from_file_location("hseo_base", Path(sys.argv[1]) / "hseo_base.py")
B = importlib.util.module_from_spec(spec); spec.loader.exec_module(B)
T = sys.argv[2]
os.environ["PATH"] = T + "/bin:" + os.environ["PATH"]; os.environ["XDG_RUNTIME_DIR"] = T + "/run"
c = B.desacoplar(["bash", "x.sh"])
assert c[:6] == ["env", f"XDG_RUNTIME_DIR={T}/run", "systemd-run", "--user", "--scope", "--quiet"] and c[-2:] == ["bash", "x.sh"], c
os.environ["HSEO_SIN_SCOPE"] = "1"; assert B.desacoplar(["bash", "x.sh"]) == ["bash", "x.sh"]
PY
exit $fail
