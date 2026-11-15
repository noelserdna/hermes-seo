"""Estar al día: versiones de Hermes y del plugin (sin modelo) y, una vez al mes, un repaso con modelo de novedades de
Hermes, MCP, plugins y SEO/GEO filtrado por una sola pregunta: ¿sube los clics o las citas en IA de las webs?

  hseo_novedades.py recoger           sin modelo, sin fetch: hermes --version frente a git ls-remote --tags (sin canary),
                                      y el commit instalado del plugin frente al de GitHub → novedades/<AAAA-MM>.json
  hseo_novedades.py proponer "<título>" "<qué aporta y a qué número>" "<riesgo>"   → puerta «adoptar» (sistema)
  hseo_novedades.py descartar "<título>" "<por qué no aporta>"                       → cuaderno, sin molestar

Nunca actualiza Hermes ni instala nada: lo que pasa el filtro llega como puerta; aprobarla solo lo apunta para una
sesión con la persona. Nunca usa git log -S/-p ni fetch en el checkout de Hermes (es un clon parcial).
"""
from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import time
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
REPO_HERMES = os.environ.get("HSEO_REPO_HERMES", "https://github.com/NousResearch/hermes-agent")
REPO_PLUGIN = os.environ.get("HSEO_REPO_PLUGIN", "https://github.com/noelserdna/hermes-seo")
MAX_MES = 3


def _sal(cmd: list, timeout: int = 60) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout).stdout
    except (OSError, subprocess.SubprocessError):
        return ""


def _version(t: str) -> tuple:
    m = re.search(r"v?(\d+)\.(\d+)\.(\d+)", t)
    return tuple(int(x) for x in m.groups()) if m else ()


def recoger() -> dict:
    instalada = _version(_sal([os.environ.get("HERMES_BIN", "hermes"), "--version"]))
    tags = [l.split("refs/tags/")[-1] for l in _sal(["git", "ls-remote", "--tags", REPO_HERMES, "v*"]).splitlines() if "refs/tags/" in l]
    # solo vX.Y.Z de verdad: fuera canary/rc y las etiquetas con fecha (v2026.9.24), que no son versiones
    estables = sorted({_version(t) for t in tags if re.fullmatch(r"v\d{1,3}\.\d{1,3}\.\d{1,3}", t) and _version(t)[0] < 100})
    ultima = estables[-1] if estables else ()
    inst = B.leer(B.home() / "instalacion.json") or {}
    commit_inst = (re.search(r"-([0-9a-f]{7,40})(?:-local)?$", str(inst.get("carpeta") or "")) or [None, ""])[1]
    head = (_sal(["git", "ls-remote", REPO_PLUGIN, "HEAD"]).split() or [""])[0][:7]
    r = {"ts": B.ahora(), "hermes": {"instalada": ".".join(map(str, instalada)) or "?", "ultima_estable": ".".join(map(str, ultima)) or "?",
                                     "hay_nueva": bool(instalada and ultima and ultima > instalada)},
         "plugin": {"instalado": commit_inst or "?", "github": head or "?", "al_dia": bool(head and commit_inst and head.startswith(commit_inst[:7]))},
         "fuentes": (B.leer(B.home() / "novedades" / "fuentes.json") or {}).get("fuentes", [])}
    d = B.home() / "novedades"
    d.mkdir(parents=True, exist_ok=True)
    B.escribir(d / f"{date.today():%Y-%m}.json", r)
    return r


def _mes() -> list:
    hoy = f"{date.today():%Y-%m}"
    return [r for r in _cargar("hseo_estado")._jsonl(B.home() / "novedades" / "propuestas.jsonl") if str(r.get("ts", "")).startswith(hoy)]


def proponer(titulo: str, aporta: str, riesgo: str) -> str:
    if len(_mes()) >= MAX_MES:
        return descartar(titulo, f"tope de {MAX_MES} propuestas al mes (aportaba: {aporta})")
    p = _cargar("hseo_puertas").abrir("__cartera__", tipo="adoptar", titulo=f"🆕 Novedad: {titulo[:80]}",
                                      texto=f"Qué aporta: {aporta}\nRiesgo: {riesgo}\n\nAprobarla solo la apunta para verla en una sesión: no se instala nada.",
                                      al_aprobar="apuntar")
    B.anotar(B.home() / "novedades" / "propuestas.jsonl", {"ts": B.ahora(), "titulo": titulo, "puerta": p["id"]})
    return f"🆕 Propuesta a la persona: {titulo} ({p['id']})"


def descartar(titulo: str, motivo: str) -> str:
    w = B.home() / "wiki" / "concepts" / "novedades-descartadas.md"
    w.parent.mkdir(parents=True, exist_ok=True)
    if not w.exists():
        w.write_text("---\ntitle: Novedades descartadas\ncreated: {0}\nupdated: {0}\ntype: concept\ntags: [decision]\n"
                     "sources: [novedades]\nconfidence: medium\n---\n\n# Novedades descartadas (no suben clics ni citas, o no ahora)\n\n".format(date.today()))
    with open(w, "a") as f:
        f.write(f"- {date.today()} · **{titulo}**: {motivo}\n")
    return f"🗑 Apuntada como descartada: {titulo}"


if __name__ == "__main__":
    a = sys.argv[1:]
    if a[:1] == ["recoger"]:
        print(json.dumps(recoger(), ensure_ascii=False, indent=1))
    elif a[:1] == ["proponer"] and len(a) == 4:
        print(proponer(*a[1:]))
    elif a[:1] == ["descartar"] and len(a) == 3:
        print(descartar(*a[1:]))
    else:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
