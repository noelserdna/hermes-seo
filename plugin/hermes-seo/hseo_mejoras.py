"""Mejoras del propio plugin, con puerta. La rama la prepara Claude Code en una sesión (o el coordinador con permiso);
aquí se comprueba y se ofrece; solo se instala lo que la persona aprueba, y siempre con vuelta atrás (volver.sh).

  hseo_mejoras.py proponer <rama>   comprueba la rama del repo del plugin: pruebas en verde, no toca lo que vigila al
                                    propio sistema (guardia, notario, instalador, cartas, aprobadores, secretos) y no pide
                                    reinicio del gateway (solo skills/, pipelines/, herramientas/, docs/) → puerta «mejora»
Tope: 3 al mes. Lo que pide reinicio o toca lo prohibido se instala a mano, en sesión.
"""
from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _cargar(nombre: str):
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, AQUI / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


B = _cargar("hseo_base")
Rechazo = B.Rechazo
MAX_MES = 3
PROHIBIDO = re.compile(r"^(encargado/guardia\.py|plugin/hermes-seo/hseo_puertas\.py|instalar\.sh|volver\.sh|encargado\.sh|"
                       r"perfiles/coordinadora\.md|encargado/SOUL\.md|latido/|correo/|copia\.sh)|aprobadores|secretos")
SIN_REINICIO = re.compile(r"^(skills/|pipelines/|herramientas/|docs/|README\.md|tests/)")


def _repo() -> Path:
    return Path(os.environ.get("HSEO_REPO") or Path.home() / "work" / "hermes-seo")


def _git(*a, cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(cwd or _repo()), *a], capture_output=True, text=True, timeout=300)


def _instalado() -> str:
    """Commit de la instalación actual (de la carpeta <versión>-<commit>), o «» si no se sabe."""
    inst = B.leer(B.home() / "instalacion.json") or {}
    m = re.search(r"-([0-9a-f]{7,40})(?:-local)?$", str(inst.get("carpeta") or ""))
    return m.group(1) if m else ""


def _detras(sha: str) -> bool:
    """¿Instalar sha perdería lo que ya está instalado? (lo instalado no es antecesor de la rama)."""
    inst = _instalado()
    return bool(inst) and _git("merge-base", "--is-ancestor", inst, sha).returncode != 0


def proponer(rama: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9._/-]{1,80}", rama):
        raise Rechazo("Nombre de rama no válido")
    hoy = f"{date.today():%Y-%m}"
    if sum(1 for r in _cargar("hseo_estado")._jsonl(B.home() / "mejoras.jsonl") if str(r.get("ts", "")).startswith(hoy)) >= MAX_MES:
        raise Rechazo(f"Ya hay {MAX_MES} mejoras propuestas este mes")
    _git("fetch", "-q", "origin", rama)
    ref = f"origin/{rama}" if _git("rev-parse", "--verify", f"origin/{rama}").returncode == 0 else rama
    sha = _git("rev-parse", ref).stdout.strip()
    if not sha:
        raise Rechazo(f"No encuentro la rama {rama}")
    if _detras(sha):
        raise Rechazo(f"La rama no parte de lo instalado ({_instalado()}): instalarla desharía cambios. Rebásala sobre main")
    base = _git("merge-base", ref, "origin/main").stdout.strip() or _git("merge-base", ref, "main").stdout.strip()
    ficheros = [f for f in _git("diff", "--name-only", f"{base}..{sha}").stdout.splitlines() if f]
    if not ficheros:
        raise Rechazo("La rama no cambia nada")
    malos = [f for f in ficheros if PROHIBIDO.search(f)]
    if malos:
        raise Rechazo("Toca lo que vigila al propio sistema (se hace en sesión con la persona): " + ", ".join(malos))
    reinicio = [f for f in ficheros if not SIN_REINICIO.search(f)]
    if reinicio:
        raise Rechazo("Pide reiniciar el gateway (se instala a mano, en sesión): " + ", ".join(reinicio))
    with tempfile.TemporaryDirectory() as t:
        wt = Path(t) / "wt"
        _git("worktree", "add", "-q", "--detach", str(wt), sha)
        try:
            r = subprocess.run(["bash", "tests/todo.sh"], cwd=wt, capture_output=True, text=True, timeout=1800)
            verde = r.returncode == 0 and "FALLA" not in r.stdout
        finally:
            _git("worktree", "remove", "--force", str(wt))
    if not verde:
        raise Rechazo("Las pruebas de la rama no pasan")
    log = _git("log", "--oneline", f"{base}..{sha}").stdout.strip()[:1500]
    p = _cargar("hseo_puertas").abrir("__cartera__", tipo="mejora", titulo=f"⬆️ Mejora del sistema: {rama}",
                                      texto=f"Qué cambia:\n{log}\n\nFicheros: {', '.join(ficheros)}\nPruebas: en verde. No pide reinicio.\n"
                                            f"Si algo va mal: volver.sh (vuelve a la instalación anterior).",
                                      al_aprobar=f"instalar:{rama}@{sha[:12]}")
    B.anotar(B.home() / "mejoras.jsonl", {"ts": B.ahora(), "rama": rama, "sha": sha, "puerta": p["id"], "ficheros": ficheros})
    return f"⬆️ Mejora propuesta a la persona: {rama} ({p['id']})"


def instalar(ref: str, firma: str) -> str:
    """Lo aprobado en la puerta: instala esa versión exacta (desacoplado) a una carpeta nueva; actual pasa a ella."""
    rama, _, sha = ref.partition("@")
    if os.environ.get("HSEO_MEJORA_SECO"):
        B.anotar(B.home() / "mejoras.jsonl", {"ts": B.ahora(), "instalada": ref, "firma": firma, "seco": True})
        return f"instalaría {ref} (en seco)"
    _git("fetch", "-q", "origin", rama)
    if _detras(sha):
        B.anotar(B.home() / "mejoras.jsonl", {"ts": B.ahora(), "rechazada": ref, "firma": firma, "motivo": "detrás de lo instalado"})
        return f"no se instala {rama}: lo instalado ({_instalado()}) es más nuevo y se perdería; hay que rebasarla y proponerla otra vez"
    log = B.home() / "logs" / f"mejora-{sha}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    guion = (f"set -e; cd {_repo()}; git fetch -q origin {rama}; d=$(mktemp -d); git worktree add -q --detach $d {sha}; "
             f"bash $d/instalar.sh --coordinadora; git worktree remove --force $d")
    subprocess.Popen(B.desacoplar(["bash", "-c", guion]), start_new_session=True, stdout=open(log, "w"), stderr=subprocess.STDOUT)
    B.anotar(B.home() / "mejoras.jsonl", {"ts": B.ahora(), "instalada": ref, "firma": firma})
    return f"instalando {rama} ({sha}); registro en logs/{log.name}; vuelta atrás: volver.sh"


if __name__ == "__main__":
    a = sys.argv[1:]
    try:
        if a[:1] == ["proponer"] and len(a) == 2:
            print(proponer(a[1]))
        else:
            print(__doc__, file=sys.stderr)
            sys.exit(2)
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        sys.exit(2)
