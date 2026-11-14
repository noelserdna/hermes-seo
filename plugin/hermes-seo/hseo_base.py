"""Utilidades comunes de hermes-seo: dónde vive el estado, lectura y escritura atómica de JSON, cerrojo entre procesos
y el error con mensaje para la persona. Copiado y adaptado de hermes-sdd (hsdd_nucleo.py).

El estado nunca vive en el repo de una web: está en HERMES_SEO_HOME (por defecto ~/.hermes/hermes-seo), fuera del
alcance de los ejecutores.
"""
from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def home() -> Path:
    """Se lee en cada llamada (no al importar) para que las pruebas y la CLI puedan cambiar HERMES_SEO_HOME."""
    return Path(os.environ.get("HERMES_SEO_HOME", Path.home() / ".hermes" / "hermes-seo"))


class Rechazo(Exception):
    """Algo que la persona (o el agente) pidió y no se puede hacer; el mensaje se le enseña tal cual."""


def leer(p: Path, defecto=None):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return defecto


def escribir(p: Path, datos, modo: int | None = None) -> None:
    """Escritura atómica (temporal + rename): un lector nunca ve un JSON a medias."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n")
    if modo is not None:
        os.chmod(tmp, modo)
    tmp.replace(p)


def anotar(p: Path, registro: dict) -> None:
    """Añade una línea a un .jsonl (los registros solo crecen)."""
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")


def ahora() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@contextlib.contextmanager
def cerrojo(nombre: str = "estado"):
    """Exclusión entre procesos (gateway, panel, CLI) para leer-modificar-escribir. Sección corta y sin esperas."""
    d = home() / ".cerrojos"
    d.mkdir(parents=True, exist_ok=True)
    with open(d / nombre, "w") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(f, fcntl.LOCK_UN)


SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{1,38}[a-z0-9]$")
RESERVADOS = {"default", "todo", "todos", "local", "cartera", "global"}


def validar_slug(slug: str) -> str:
    if not isinstance(slug, str) or not SLUG.match(slug) or "--" in slug:
        raise Rechazo("El nombre corto de la web va en minúsculas, con letras, números y guiones (3-40 caracteres)")
    if slug in RESERVADOS:
        raise Rechazo(f"«{slug}» es un nombre reservado")
    return slug
