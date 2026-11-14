"""Publicar lo aprobado en una puerta, con el adaptador de cada web. Solo lo llama el notario (hseo_puertas.firmar),
nunca un agente.

Lee publicacion.json del encargo (lo deja la etapa «preparar» o «aplicar-cambio») y el contenido (borrador.md):

  repo-pr     rama nueva en el repo de la web, el fichero en su carpeta de contenido, commit, push y PR. Si la web
              tiene un script de despliegue (capacidades.publicacion.desplegar), se lanza con el número del PR.
              cliente.json → capacidades.publicacion: {repo, rama (main), contenido_dir (p. ej. src/content/blog),
              extension (.md), frontmatter: {campo: plantilla con {titulo} {meta_descripcion} {fecha} {slug}…},
              autor_git: "Nombre <correo>", borrador_pr (true), desplegar: "ruta/script {pr}"}
  wordpress   entrada (o página) por la API REST con contraseña de aplicación (WP_USUARIO, WP_APP_PASSWORD en los
              secretos del cliente). capacidades.publicacion: {url_api, tipo (posts|pages), estado (publish|draft)}
  entrega     un paquete con los cambios exactos para quien lleve la web (clientes/<web>/entregas/<encargo>/)

Cada publicación queda en clientes/<web>/cambios.jsonl (clase, hipótesis, URL, fecha): de ahí sale el veredicto.
"""
from __future__ import annotations

import base64
import html
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone
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
Rechazo = B.Rechazo


# ── el contenido ────────────────────────────────────────────────────────────────────────────────────────────────────
def _leer_publicacion(slug: str, eid: str) -> tuple:
    d = E.carpeta(slug, eid)
    pub = B.leer(d / "publicacion.json")
    if not isinstance(pub, dict):
        raise Rechazo("Falta publicacion.json en el encargo (la etapa «preparar» no lo dejó)")
    cuerpo, meta = "", {}
    if pub.get("contenido"):
        f = (d / pub["contenido"]).resolve()
        if not str(f).startswith(str(d.resolve())) or not f.exists():
            raise Rechazo(f"No encuentro el contenido {pub['contenido']}")
        meta, cuerpo = separar_cabecera(f.read_text())
    return pub, meta, cuerpo


def separar_cabecera(texto: str) -> tuple:
    """Bloque inicial «---\\nclave: valor\\n---» del borrador → (dict, resto)."""
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n?(.*)$", texto, re.S)
    if not m:
        return {}, texto
    meta = {}
    for linea in m.group(1).splitlines():
        if ":" in linea:
            k, v = linea.split(":", 1)
            meta[k.strip()] = v.strip().strip('"')
    return meta, m.group(2)


def slug_de(pub: dict, meta: dict) -> str:
    url = pub.get("url") or meta.get("url") or ""
    s = url.rstrip("/").rsplit("/", 1)[-1] if url else (pub.get("titulo") or meta.get("titulo") or "pieza")
    s = re.sub(r"\.(html?|md|mdx)$", "", s.lower())
    s = re.sub(r"[áàä]", "a", s); s = re.sub(r"[éèë]", "e", s); s = re.sub(r"[íìï]", "i", s)
    s = re.sub(r"[óòö]", "o", s); s = re.sub(r"[úùü]", "u", s); s = s.replace("ñ", "n")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")[:80] or "pieza"


def markdown_a_html(md: str) -> str:
    """Markdown sencillo → HTML (títulos, párrafos, listas, citas, código, enlaces, negrita, cursiva, código en
    línea). Suficiente para publicar un borrador en WordPress; lo raro se queda como texto."""
    def enlinea(t: str) -> str:
        t = html.escape(t, quote=False)
        t = re.sub(r"`([^`]+)`", r"<code>\1</code>", t)
        t = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", t)
        t = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\w)", r"<em>\1</em>", t)
        t = re.sub(r"\[([^\]]+)\]\((https?://[^)\s]+|/[^)\s]*)\)", lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', t)
        return t
    out, lista, parrafo, codigo = [], None, [], None
    def cerrar():
        nonlocal lista, parrafo
        if parrafo:
            out.append(f"<p>{enlinea(' '.join(parrafo))}</p>"); parrafo = []
        if lista:
            out.append(f"</{lista}>"); lista = None
    for linea in md.splitlines():
        if codigo is not None:
            if linea.strip().startswith("```"):
                out.append(f"<pre><code>{html.escape(chr(10).join(codigo))}</code></pre>"); codigo = None
            else:
                codigo.append(linea)
            continue
        if linea.strip().startswith("```"):
            cerrar(); codigo = []; continue
        m = re.match(r"^(#{1,6})\s+(.*)$", linea)
        if m:
            cerrar(); n = len(m.group(1)); out.append(f"<h{n}>{enlinea(m.group(2).strip())}</h{n}>"); continue
        m = re.match(r"^\s*([-*]|\d+\.)\s+(.*)$", linea)
        if m:
            tipo = "ol" if m.group(1)[0].isdigit() else "ul"
            if parrafo:
                out.append(f"<p>{enlinea(' '.join(parrafo))}</p>"); parrafo = []
            if lista != tipo:
                if lista:
                    out.append(f"</{lista}>")
                out.append(f"<{tipo}>"); lista = tipo
            out.append(f"<li>{enlinea(m.group(2))}</li>"); continue
        if linea.startswith(">"):
            cerrar(); out.append(f"<blockquote><p>{enlinea(linea.lstrip('> '))}</p></blockquote>"); continue
        if not linea.strip():
            cerrar(); continue
        if lista:
            out.append(f"</{lista}>"); lista = None
        parrafo.append(linea.strip())
    cerrar()
    if codigo is not None:
        out.append(f"<pre><code>{html.escape(chr(10).join(codigo))}</code></pre>")
    return "\n".join(out)


def _anotar_cambio(slug: str, eid: str, pub: dict, adaptador: str, resultado: str, firma: str) -> None:
    B.anotar(C.carpeta(slug) / "cambios.jsonl", {
        "id": f"c-{eid}", "ts": B.ahora(), "encargo": eid, "clase": pub.get("clase") or pub.get("tipo"),
        "hipotesis": pub.get("hipotesis", ""), "url": pub.get("url", ""),
        "urls": [c.get("url") for c in pub.get("cambios") or [] if c.get("url")], "adaptador": adaptador,
        "resultado": resultado, "firma": firma})


def _antes_de_publicar(slug: str, cfg: dict) -> None:
    """Política del cliente: un script que, si sale con error, impide publicar ahora (p. ej. una ventana en la que la
    web sirve una copia). Su salida es el motivo."""
    script = (cfg.get("politicas") or {}).get("antes_de_publicar")
    if not script:
        return
    ruta = (C.carpeta(slug) / "extensiones" / script).resolve()
    if not str(ruta).startswith(str((C.carpeta(slug) / "extensiones").resolve())) or not ruta.exists():
        raise Rechazo(f"No encuentro la comprobación «{script}» en las extensiones del cliente")
    r = subprocess.run(["bash", str(ruta)], capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise Rechazo(f"Ahora no se puede publicar: {(r.stdout or r.stderr).strip()[-300:]}")


# ── adaptadores ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _git(repo, *args, env=None) -> str:
    r = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, timeout=300, env=env)
    if r.returncode != 0:
        raise Rechazo(f"git {args[0]} falló: {(r.stderr or r.stdout).strip()[-300:]}")
    return r.stdout.strip()


def repo_pr(slug: str, eid: str, cfg: dict, pub: dict, meta: dict, cuerpo: str, firma: str) -> str:
    conf = cfg["capacidades"]["publicacion"]
    repo = Path(os.path.expanduser(conf["repo"]))
    if not (repo / ".git").exists():
        raise Rechazo(f"{repo} no es un repositorio git")
    rama_base = conf.get("rama", "main")
    rama = f"hseo/{eid}"
    wt = C.carpeta(slug) / "wt" / eid
    if wt.exists():
        shutil.rmtree(wt)
    try:
        _git(repo, "fetch", "-q", "origin", rama_base)
        base = f"origin/{rama_base}"
    except Rechazo:
        base = rama_base
    _git(repo, "worktree", "add", "-q", "-B", rama, str(wt), base)
    if pub.get("tipo") == "cambio-tecnico":
        cambios = wt / ".hseo-cambios.json"   # el cambio técnico lo aplica el script de la web o una persona en el PR
        cambios.write_text(json.dumps(pub.get("cambios") or [], ensure_ascii=False, indent=2) + "\n")
        fichero = cambios
    else:
        s = slug_de(pub, meta)
        destino = wt / conf.get("contenido_dir", "content") / f"{s}{conf.get('extension', '.md')}"
        valores = {**meta, **{k: v for k, v in pub.items() if isinstance(v, str)}, "slug": s,
                   "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d")}
        plantilla = conf.get("frontmatter") or {"title": "{titulo}", "description": "{meta_descripcion}", "date": "{fecha}"}
        def rellenar(v) -> str:
            return re.sub(r"{(\w+)}", lambda m: str(valores.get(m.group(1), "")), str(v))
        cab = ["---"] + [k + ": " + json.dumps(rellenar(v), ensure_ascii=False) for k, v in plantilla.items()] + ["---", ""]
        destino.parent.mkdir(parents=True, exist_ok=True)
        if pub.get("tipo") == "actualizacion" and destino.exists():
            viejo_meta, _ = separar_cabecera(destino.read_text())
            if viejo_meta:   # conserva la cabecera de la página que ya existe
                cab = ["---"] + [f"{k}: {v}" for k, v in viejo_meta.items()] + ["---", ""]
        destino.write_text("\n".join(cab) + cuerpo.strip() + "\n")
        fichero = destino
    autor = conf.get("autor_git") or "hermes-seo <hermes-seo@localhost>"
    nombre, correo = (re.match(r"^(.*?)\s*<(.+)>$", autor) or re.match(r"(.*)()", autor)).groups()
    _git(wt, "add", str(fichero.relative_to(wt)))
    _git(wt, "-c", f"user.name={nombre}", "-c", f"user.email={correo or 'hermes-seo@localhost'}", "commit", "-q", "-m",
         f"{'content' if pub.get('tipo') != 'cambio-tecnico' else 'seo'}: {pub.get('titulo') or meta.get('titulo') or eid}")
    secretos = C.secretos(slug)
    env = {**os.environ, **({"GH_TOKEN": secretos["GH_TOKEN"]} if secretos.get("GH_TOKEN") else {})}
    _git(wt, "push", "-q", "-u", "origin", rama, env=env)
    cuerpo_pr = (f"Clase: {pub.get('clase') or pub.get('tipo')}\nHipótesis: {pub.get('hipotesis', '')}\n\n"
                 f"Aprobado en la puerta por {firma}. Encargo {eid} (hermes-seo).")
    args = ["gh", "pr", "create", "--head", rama, "--base", rama_base, "--title",
            pub.get("titulo") or meta.get("titulo") or eid, "--body", cuerpo_pr]
    if conf.get("borrador_pr", False):
        args.append("--draft")
    r = subprocess.run(args, capture_output=True, text=True, cwd=str(wt), timeout=120, env=env)
    if r.returncode != 0:
        raise Rechazo(f"gh pr create falló: {(r.stderr or r.stdout).strip()[-300:]}")
    url_pr = r.stdout.strip().splitlines()[-1]
    resultado = f"PR {url_pr}"
    if conf.get("desplegar"):
        numero = url_pr.rstrip("/").rsplit("/", 1)[-1]
        script = conf["desplegar"].replace("{pr}", numero)
        partes = script.split()
        ruta = (C.carpeta(slug) / "extensiones" / partes[0]).resolve()
        if not str(ruta).startswith(str((C.carpeta(slug) / "extensiones").resolve())) or not ruta.exists():
            raise Rechazo(f"PR abierto ({url_pr}), pero no encuentro el script de despliegue {partes[0]} en las extensiones")
        subprocess.Popen(["bash", str(ruta), *partes[1:]], start_new_session=True, cwd=str(repo), env=env,
                         stdout=open(C.carpeta(slug) / "logs" / f"desplegar-{eid}.log", "w"), stderr=subprocess.STDOUT)
        resultado += " · despliegue lanzado"
    return resultado


def wordpress(slug: str, eid: str, cfg: dict, pub: dict, meta: dict, cuerpo: str, firma: str) -> str:
    conf = cfg["capacidades"]["publicacion"]
    if pub.get("tipo") == "cambio-tecnico":
        return entrega(slug, eid, cfg, pub, meta, cuerpo, firma) + " (WordPress: los cambios técnicos se aplican a mano)"
    s = C.secretos(slug)
    if not s.get("WP_USUARIO") or not s.get("WP_APP_PASSWORD"):
        raise Rechazo("Faltan WP_USUARIO y WP_APP_PASSWORD en los secretos de la web")
    base = conf["url_api"].rstrip("/")
    tipo = conf.get("tipo", "posts")
    auth = base64.b64encode(f"{s['WP_USUARIO']}:{s['WP_APP_PASSWORD']}".encode()).decode()
    cab = {"Authorization": f"Basic {auth}", "Content-Type": "application/json", "User-Agent": "hermes-seo/0.1"}

    def pedir(metodo: str, ruta: str, datos=None):
        req = urllib.request.Request(f"{base}{ruta}", method=metodo, headers=cab,
                                     data=json.dumps(datos).encode() if datos is not None else None)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raise Rechazo(f"WordPress respondió {e.code}: {e.read()[:200].decode(errors='replace')}")
        except OSError as e:
            raise Rechazo(f"No pude hablar con WordPress: {e}")

    sl = slug_de(pub, meta)
    datos = {"title": pub.get("titulo") or meta.get("titulo") or sl, "content": markdown_a_html(cuerpo),
             "excerpt": pub.get("meta_descripcion") or meta.get("meta_descripcion", ""), "slug": sl,
             "status": conf.get("estado", "publish")}
    existente = None
    if pub.get("tipo") == "actualizacion":
        encontrados = pedir("GET", f"/wp/v2/{tipo}?slug={sl}&status=any") or []
        existente = encontrados[0]["id"] if encontrados else None
        if not existente:
            raise Rechazo(f"No encuentro en WordPress la página «{sl}» que había que actualizar")
    r = pedir("POST", f"/wp/v2/{tipo}/{existente}" if existente else f"/wp/v2/{tipo}", datos)
    return f"WordPress {'actualizada' if existente else 'publicada'}: {r.get('link') or r.get('id')}"


def entrega(slug: str, eid: str, cfg: dict, pub: dict, meta: dict, cuerpo: str, firma: str) -> str:
    d = C.carpeta(slug) / "entregas" / eid
    d.mkdir(parents=True, exist_ok=True)
    lineas = [f"# Cambios para {cfg['nombre']} ({cfg['url']})", "",
              f"Aprobado por {firma} el {datetime.now(timezone.utc).strftime('%d-%m-%Y')}.", ""]
    if pub.get("tipo") == "cambio-tecnico":
        lineas += ["## Qué cambiar", ""]
        for i, c in enumerate(pub.get("cambios") or [], 1):
            lineas += [f"{i}. **{c.get('accion', 'cambio')}** en {c.get('url', '')}",
                       f"   - Antes: {c.get('antes', '—')}", f"   - Después: {c.get('despues', '—')}", ""]
        if pub.get("como_deshacer"):
            lineas += ["## Cómo deshacerlo", "", pub["como_deshacer"], ""]
    else:
        lineas += ["## Qué publicar", "",
                   f"- Dirección: {pub.get('url') or '(nueva: ' + slug_de(pub, meta) + ')'}",
                   f"- Título (etiqueta title): {pub.get('titulo') or meta.get('titulo', '')}",
                   f"- Meta descripción: {pub.get('meta_descripcion') or meta.get('meta_descripcion', '')}",
                   f"- Contenido: `contenido.md` (Markdown) o `contenido.html`", ""]
        (d / "contenido.md").write_text(cuerpo.strip() + "\n")
        (d / "contenido.html").write_text(markdown_a_html(cuerpo) + "\n")
    lineas += ["## Por qué", "", pub.get("hipotesis") or "—", ""]
    (d / "LEEME.md").write_text("\n".join(lineas))
    return f"paquete listo para quien lleve la web: {d}"


ADAPTADORES = {"repo-pr": repo_pr, "wordpress": wordpress, "entrega": entrega}


def publicar(slug: str, eid: str, firma: str) -> str:
    cfg = C.leer(slug)
    ad = (cfg["capacidades"].get("publicacion") or {}).get("adaptador", "ninguno")
    if ad not in ADAPTADORES:
        raise Rechazo(f"{cfg['nombre']} no tiene configurado cómo publicar (capacidades.publicacion.adaptador)")
    if (cfg.get("politicas") or {}).get("pausado") or (B.home() / "pausa").exists():
        raise Rechazo(f"{cfg['nombre']} está en pausa: no se publica")
    _antes_de_publicar(slug, cfg)
    pub, meta, cuerpo = _leer_publicacion(slug, eid)
    if pub.get("tipo") != "cambio-tecnico" and not cuerpo.strip():
        raise Rechazo("El contenido está vacío")
    resultado = ADAPTADORES[ad](slug, eid, cfg, pub, meta, cuerpo, firma)
    _anotar_cambio(slug, eid, pub, ad, resultado, firma)
    return resultado
