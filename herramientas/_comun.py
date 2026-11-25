"""Piezas comunes de las herramientas de datos de hermes-seo.

Cada herramienta recibe --cliente <slug>, lee su cliente.json y sus claves con el plugin (plugin/hermes-seo/) y deja
sus datos en HERMES_SEO_HOME/clientes/<slug>/datos/<fuente>/. Las claves nunca se imprimen: cualquier texto de error
pasa por tapar() antes de salir.

Códigos de salida comunes: 2 = falta configuración o argumento, 3 = falta una clave (o el acceso ha caducado).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import os
import re
import sys
import time
from pathlib import Path

ARNES = Path(__file__).resolve().parent.parent
PLUGIN = ARNES / "plugin" / "hermes-seo"
UA = "hermes-seo/0.1 (+https://github.com/noelserdna/hermes-seo)"


def cargar(nombre: str):
    """Módulos del plugin sin paquete instalable, igual que hseo_clientes._cargar."""
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, PLUGIN / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


C = cargar("hseo_clientes")
B = cargar("hseo_base")

_CLAVES_VISTAS: list = []


def parser(descripcion: str) -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=descripcion, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cliente", required=True, help="nombre corto (slug) del cliente")
    return ap


def fallar(mensaje: str, codigo: int = 2, prefijo: str = "") -> None:
    print(tapar(f"{prefijo}{mensaje}"), file=sys.stderr)
    if prefijo:   # las herramientas con «última línea» la dan también por la salida estándar
        print(tapar(f"{prefijo}{mensaje}"))
    sys.exit(codigo)


def cliente(slug: str) -> dict:
    try:
        return C.leer(slug)
    except B.Rechazo as e:
        fallar(str(e), 2)


def clave(slug: str, nombre: str, prefijo: str = "") -> str:
    """Una clave de secretos.env (del cliente o global). Si falta, sale con código 3 sin mostrar nada de ella."""
    valor = C.secretos(slug).get(nombre, "")
    if not valor:
        fallar(f"falta {nombre} en {C.carpeta(slug) / 'secretos.env'} (o en {B.home() / 'secretos.env'})", 3, prefijo)
    _CLAVES_VISTAS.append(valor)
    return valor


def tapar(texto: str) -> str:
    """Quita de un texto cualquier clave leída (por si un error de red repite la URL o una cabecera)."""
    for v in _CLAVES_VISTAS:
        if v and len(v) >= 4:
            texto = texto.replace(v, "***")
    return texto


def datos(slug: str, fuente: str) -> Path:
    d = C.carpeta(slug) / "datos" / fuente
    d.mkdir(parents=True, exist_ok=True)
    return d


def hoy() -> str:
    return dt.date.today().isoformat()


def modelos_ia(cfg: dict, motor: str, defecto: str) -> list:
    """Modelos con los que se pregunta a un motor de IA: cliente.json → ia.modelos.<motor> (el primero es el
    principal), o solo el de la herramienta. Sirve para comparar lo que ve quien paga con lo que ve quien usa la
    versión gratuita o un modelo pequeño."""
    m = ((cfg.get("ia") or {}).get("modelos") or {}).get(motor) if isinstance(cfg.get("ia"), dict) else None
    return [str(x) for x in m] if isinstance(m, list) and m else [defecto]


def salida_ia(slug: str, cfg: dict, motor: str, modelo: str, defecto: str) -> Path:
    """datos/ia/<motor>-<fecha>.json con el modelo principal; con otro, <motor>-<modelo>-<fecha>.json."""
    principal = modelos_ia(cfg, motor, defecto)[0]
    etiqueta = "" if modelo == principal else "-" + re.sub(r"[^a-z0-9.]+", "-", modelo.lower()).strip("-")
    return datos(slug, "ia") / f"{motor}{etiqueta}-{hoy()}.json"


def url_base(variable: str, defecto: str) -> str:
    """URL base de una API; las pruebas la cambian por la de un servidor local falso."""
    return (os.environ.get(variable) or defecto).rstrip("/")


def pausa(segundos: float) -> None:
    """Pausas de cortesía con las API (límites de peticiones); HSEO_SIN_PAUSAS=1 las quita en las pruebas."""
    if os.environ.get("HSEO_SIN_PAUSAS") != "1":
        time.sleep(segundos)


def mercado_principal(cfg: dict) -> tuple:
    """(país en mayúsculas, idioma) del primer mercado del cliente: lo que usan Brave y ChatGPT."""
    m = (cfg.get("mercados") or [{}])[0]
    return str(m.get("pais") or "ES").upper(), str(cfg.get("idioma") or "es")


def es_nuestro(netloc: str, dominio: str) -> bool:
    n = netloc.lower().split(":")[0]
    d = dominio.lower()
    return n == d or n.endswith("." + d)


def leer_preguntas(archivo: Path) -> list:
    import re
    if not archivo.exists():
        fallar(f"no encuentro el archivo de preguntas {archivo} (una por línea, numeradas «1. …»; o usa --preguntas)", 2)
    return [m.group(1).strip() for m in re.finditer(r"^\d+\.\s+(.+)$", archivo.read_text(), re.M)]
