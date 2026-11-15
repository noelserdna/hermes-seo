"""Salud del servidor (lo que no es de ninguna web): disco, copia, panel y que la vigilancia de cada web siga viva.

Dos piezas, a propósito separadas:
  revisar   lo ejecuta el crontab del usuario (FUERA de Hermes, cada 10 min): detecta y repara con una lista cerrada
            (disco: limpia registros y cachés regenerables y aligera los worktrees en puerta; copia: la repite; panel:
            lo reinicia). Como mucho 3 reparaciones al día. Deja HERMES_SEO_HOME/sistema.json.
  avisos    lo ejecuta un cron --no-agent de la coordinadora: lee sistema.json y avisa SOLO de lo que no se arregló
            (una vez por problema), de que revisar dejó de correr o de que la vigilancia de una web se paró.
Si cae el propio Hermes avisa el latido externo (latido/), no esto.

  hseo_sistema.py revisar [--seco]   ·   hseo_sistema.py avisos
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
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
C = _cargar("hseo_clientes")
MAX_REPARACIONES_DIA = 3


def _corre(cmd: list, timeout: int = 600) -> str:
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return "ok" if r.returncode == 0 else f"salió con {r.returncode}: {(r.stderr or r.stdout).strip()[-150:]}"
    except (OSError, subprocess.SubprocessError) as e:
        return f"no se pudo: {e}"


def _hoy_reparaciones(estado: dict) -> int:
    hoy = time.strftime("%Y-%m-%d")
    return sum(1 for r in estado.get("historial", []) if str(r.get("ts", "")).startswith(hoy))


def _reparar_disco(seco: bool) -> str:
    hechos = []
    if seco:
        return "en seco"
    if shutil.which("journalctl"):
        hechos.append("registros: " + _corre(["sudo", "-n", "journalctl", "--vacuum-size=300M"]))
    if shutil.which("pnpm"):
        hechos.append("pnpm: " + _corre(["pnpm", "store", "prune"]))
    uv = shutil.which("uv") or str(Path.home() / ".local/bin/uv")
    if os.path.exists(uv):
        hechos.append("uv: " + _corre([uv, "cache", "prune"]))
    PUB, E = _cargar("hseo_publicacion"), _cargar("hseo_encargos")
    n = 0
    for slug in C.listar():
        for e in E.listar(slug, abiertos=True):
            if e.get("estado") == "en-puerta":
                try:
                    n += len(PUB.aligerar(slug, e["id"]))
                except Exception:   # noqa: BLE001
                    pass
    hechos.append(f"worktrees aligerados: {n}")
    return "; ".join(hechos)


def revisar(seco: bool = False, ahora: float | None = None) -> dict:
    ahora = ahora or time.time()
    f = B.home() / "sistema.json"
    estado = B.leer(f) or {}
    problemas, reparaciones = [], []
    puede = _hoy_reparaciones(estado) < MAX_REPARACIONES_DIA

    for x in B.disco():
        if x["aviso"]:
            if puede:
                r = _reparar_disco(seco)
                reparaciones.append({"ts": B.ahora(), "que": "disco", "resultado": r})
                puede = _hoy_reparaciones({"historial": estado.get("historial", []) + reparaciones}) < MAX_REPARACIONES_DIA
            sigue = [y for y in B.disco() if y["punto"] == x["punto"] and y["aviso"]]
            if sigue:
                problemas.append({"firma": f"disco-{x['punto']}", "texto": f"el disco {x['punto']} está al {sigue[0]['usado_pct']} % ({sigue[0]['libres_gb']} GB libres)"})

    cop = B.leer(B.home() / "copia.json")
    copia_sh = Path(B.home()) / "actual" / "copia.sh"
    if isinstance(cop, dict) and (not cop.get("ok") or ahora - _ts(cop.get("ts")) > 26 * 3600):
        if puede and copia_sh.exists() and not seco:
            r = _corre(["bash", str(copia_sh)], timeout=900)
            reparaciones.append({"ts": B.ahora(), "que": "copia", "resultado": r})
            cop = B.leer(B.home() / "copia.json")
        if not isinstance(cop, dict) or not cop.get("ok") or ahora - _ts(cop.get("ts")) > 26 * 3600:
            problemas.append({"firma": "copia", "texto": f"la copia diaria no se hizo bien ({(cop or {}).get('motivo') or 'tiene más de un día'})"})

    if shutil.which("systemctl"):
        act = subprocess.run(["systemctl", "is-active", "hermes-dashboard"], capture_output=True, text=True).stdout.strip()
        if act and act not in ("active", "activating", "unknown"):
            if puede and not seco:
                reparaciones.append({"ts": B.ahora(), "que": "panel", "resultado": _corre(["sudo", "-n", "systemctl", "restart", "hermes-dashboard"])})
                act = subprocess.run(["systemctl", "is-active", "hermes-dashboard"], capture_output=True, text=True).stdout.strip()
            if act != "active":
                problemas.append({"firma": "panel", "texto": f"el panel está «{act}»"})

    out = {"ts": B.ahora(), "problemas": problemas, "reparaciones": reparaciones,
           "historial": (estado.get("historial", []) + reparaciones)[-50:]}
    B.escribir(f, out)
    return out


def _ts(t) -> float:
    return _cargar("hseo_estado")._ts(t)


def avisos(ahora: float | None = None) -> list:
    """Lo que hay que contar a la persona (una vez por problema; nada si todo va bien o ya se dijo)."""
    ahora = ahora or time.time()
    s = B.leer(B.home() / "sistema.json")
    vistos_f = B.home() / "sistema-avisos.json"
    vistos = B.leer(vistos_f) or {}
    actuales = {}
    if not isinstance(s, dict):
        actuales["sin-revisar"] = "la revisión del sistema no ha corrido nunca (falta en el crontab: hseo_sistema.py revisar)"
    else:
        if ahora - _ts(s.get("ts")) > 30 * 60:
            actuales["sin-revisar"] = f"la revisión del sistema no corre desde {str(s.get('ts'))[:16]} (crontab del usuario)"
        for p in s.get("problemas", []):
            rep = [r for r in s.get("reparaciones", []) if p["firma"].startswith(r["que"])]
            actuales[p["firma"]] = p["texto"] + (f". Ya probé: {rep[-1]['resultado'][:200]}" if rep else "")
    sal = sorted((B.home() / "correo" / "salida").glob("*.json")) if (B.home() / "correo" / "salida").is_dir() else []
    if sal and ahora - sal[0].stat().st_mtime > 10 * 60:
        err = (B.leer(sal[0]) or {}).get("error", "")
        actuales["correo"] = f"hay {len(sal)} correo(s) sin salir desde hace más de 10 min{(': ' + err) if err else ''}"
    for slug in C.listar():
        v = B.leer(C.carpeta(slug) / "vigilancia.json")
        if isinstance(v, dict) and ahora - _ts(v.get("ts")) > 15 * 60:
            actuales[f"vigilancia-{slug}"] = f"la vigilancia de {slug} no corre desde {str(v.get('ts'))[:16]}"
    lineas = [f"⚙️ {t}." for k, t in actuales.items() if k not in vistos]
    B.escribir(vistos_f, {k: vistos.get(k, B.ahora()) for k in actuales})   # lo resuelto se olvida: si vuelve, se avisa
    return lineas


def main(argv=None) -> int:
    a = argv if argv is not None else sys.argv[1:]
    if a[:1] == ["revisar"]:
        r = revisar(seco="--seco" in a)
        if "--seco" in a:
            print(json.dumps(r, ensure_ascii=False, indent=1))
    elif a[:1] == ["avisos"]:
        for l in avisos():
            print(l)
    else:
        print(__doc__, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
