"""Revisión mecánica del encargado en cada puerta (sin IA). Copiado y adaptado de hermes-sdd (hsdd_revision.py).

Sale arriba del texto de la puerta como «🧭 Encargado: N aviso(s)». No bloquea a la persona, pero **un aviso grave
impide que Jev apruebe solo** (y el notario lo vuelve a comprobar).

  hseo_revision.py revisar <web> <encargo> <tipo>

Cada aviso: {grave: bool, codigo, texto}. Cada regla nueva se calibra antes contra encargos reales: un aviso grave
falso le quita a Jev decisiones que podría tomar.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
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
E = _cargar("hseo_encargos")


def _veredicto(f: Path) -> str:
    """APROBADO | CAMBIOS | "" según la última línea «VEREDICTO: …» del fichero."""
    try:
        m = re.findall(r"VEREDICTO:\s*\**\s*(APROBADO|CAMBIOS)", f.read_text(errors="replace"), re.I)
    except OSError:
        return ""
    return m[-1].upper() if m else ""


def _aviso(lista: list, grave: bool, codigo: str, texto: str) -> None:
    lista.append({"grave": grave, "codigo": codigo, "texto": texto})


def _publicar(slug: str, d: Path, avisos: list) -> None:
    pub = B.leer(d / "publicacion.json")
    if not isinstance(pub, dict):
        _aviso(avisos, True, "sin-publicacion", "No hay una publicación preparada válida (publicacion.json)")
        return
    if pub.get("tipo") not in ("nuevo", "actualizacion", "cambio-tecnico"):
        _aviso(avisos, True, "publicacion-sin-tipo", "publicacion.json no dice qué se publica (tipo nuevo, actualizacion o cambio-tecnico)")
    conf = (C.leer(slug).get("capacidades") or {}).get("publicacion") or {}
    if conf.get("adaptador") == "repo-pr" and conf.get("desplegar") and not (pub.get("pr") or pub.get("pr_url")) \
            and pub.get("contenido") is None:
        _aviso(avisos, True, "sin-pr", "La web publica por PR y la publicación no trae ni el PR ni el contenido")
    for f, quien in (("verificacion.md", "La verificación de datos"), ("lectura.md", "La revisión de lectura")):
        if (d / f).exists():
            v = _veredicto(d / f)
            if v == "CAMBIOS":
                _aviso(avisos, f == "verificacion.md", f"{f[:-3]}-cambios", f"{quien} pidió cambios")
            elif not v:
                _aviso(avisos, f == "verificacion.md", f"{f[:-3]}-sin-veredicto", f"{quien} no dejó veredicto")
        elif f == "verificacion.md":
            _aviso(avisos, True, "sin-verificar", "Nadie verificó los datos")
    if pub.get("tipo") == "cambio-tecnico":
        _tecnico(pub, avisos)
        return
    contenido = d / str(pub.get("contenido") or "borrador.md")
    texto = contenido.read_text(errors="replace") if contenido.exists() else ""
    meta = {}
    m = re.match(r"^---\s*\n(.*?)\n---", texto, re.S)
    if m:
        for linea in m.group(1).splitlines():
            if ":" in linea:
                k, v = linea.split(":", 1)
                meta[k.strip()] = v.strip().strip('"')
    cuerpo = texto[m.end():] if m else texto
    if len(cuerpo.split()) < 150:
        _aviso(avisos, True, "contenido-corto", f"El contenido tiene {len(cuerpo.split())} palabras")
    titulo = pub.get("titulo") or meta.get("titulo") or ""
    if not titulo:
        _aviso(avisos, True, "sin-titulo", "No tiene título")
    elif not 30 <= len(titulo) <= 60:
        _aviso(avisos, False, "titulo-largo", f"El título tiene {len(titulo)} caracteres (mejor entre 30 y 60)")
    desc = pub.get("meta_descripcion") or meta.get("meta_descripcion") or ""
    if not desc:
        _aviso(avisos, False, "sin-meta", "No tiene meta descripción")
    elif len(desc) > 165:
        _aviso(avisos, False, "meta-larga", f"La meta descripción tiene {len(desc)} caracteres (Google corta hacia 160)")
    if not pub.get("hipotesis"):
        _aviso(avisos, False, "sin-hipotesis", "No dice qué se espera conseguir (sin hipótesis no habrá veredicto)")
    if len(re.findall(r"^#\s", cuerpo, re.M)) > 1:
        _aviso(avisos, False, "varios-h1", "Tiene más de un título principal (#)")
    # canibalización: otra URL ya publicada para la misma búsqueda principal
    busqueda = (pub.get("busqueda_principal") or meta.get("busqueda_principal") or "").strip().lower()
    url = (pub.get("url") or meta.get("url") or "").rstrip("/")
    if busqueda:
        try:
            for linea in (C.carpeta(slug) / "cambios.jsonl").read_text().splitlines():
                r = json.loads(linea)
                otro = (r.get("url") or "").rstrip("/")
                if otro and otro != url and busqueda in json.dumps(r, ensure_ascii=False).lower():
                    _aviso(avisos, False, "canibalizacion", f"«{busqueda}» ya se trabajó en {otro}")
                    break
        except OSError:
            pass


def _tecnico(pub: dict, avisos: list) -> None:
    cambios = pub.get("cambios") or []
    if not cambios:
        _aviso(avisos, True, "sin-cambios", "No dice qué cambiar")
    if not pub.get("hipotesis"):
        _aviso(avisos, True, "sin-hipotesis", "Un cambio técnico sin hipótesis medible no se aprueba solo")
    if not pub.get("como_deshacer"):
        _aviso(avisos, False, "sin-deshacer", "No dice cómo deshacerlo")
    for c in cambios:
        if c.get("accion") == "redireccion" and str(c.get("antes", "")).rstrip("/") == str(c.get("despues", "")).rstrip("/"):
            _aviso(avisos, True, "redireccion-bucle", f"La redirección de {c.get('antes')} apunta a sí misma")
        if c.get("accion") in ("eliminar", "noindex"):
            _aviso(avisos, True, "quita-paginas", f"Quita o desindexa {c.get('url')}: lo decide una persona")


def revisar(slug: str, eid: str | None, tipo: str) -> dict:
    avisos: list = []
    if eid:
        d = E.carpeta(slug, eid)
        if tipo in ("publicar", "cambio-tecnico"):
            _publicar(slug, d, avisos)
        enc = E.leer(slug, eid)
        if enc.get("saltadas"):
            _aviso(avisos, False, "etapas-saltadas",
                   "Se saltaron etapas por falta de configuración: " + ", ".join(s["id"] for s in enc["saltadas"]))
    return {"avisos": avisos, "graves": sum(1 for a in avisos if a["grave"])}


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) != 4 or a[0] != "revisar":
        print("uso: hseo_revision.py revisar <web> <encargo> <tipo>", file=sys.stderr)
        sys.exit(2)
    print(json.dumps(revisar(a[1], a[2], a[3]), ensure_ascii=False, indent=2))
