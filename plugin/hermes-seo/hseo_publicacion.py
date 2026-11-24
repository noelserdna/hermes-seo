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
  mcp         el artículo (y sus traducciones, enlazadas) por el servidor MCP de la propia web (hseo_mcp: acceso
              aprobado por una persona con un código). capacidades.publicacion: {url, guardar: {herramienta, args:
              plantilla}, id, url_resultado, reglas}. Con capacidades.publicacion.seo, un cambio técnico que solo toca
              títulos y metas de páginas ya publicadas se aplica en vivo (seo_mcp); los demás cambios técnicos, entrega.

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
import time
import sys
import urllib.parse
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
    if not pub.get("pr") and pub.get("pr_url"):   # sinónimo frecuente
        pub["pr"] = pub["pr_url"]
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
    try:
        _cargar("hseo_wiki").regenerar_cambios(slug)
    except Exception:   # noqa: BLE001 — la memoria nunca frena una publicación
        pass


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
    if pub.get("pr"):   # la etapa de la web ya abrió el PR con sus convenciones: aquí solo se despliega
        return _desplegar(slug, eid, conf, repo, str(pub["pr"]), firma=firma)
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
    return _desplegar(slug, eid, conf, repo, r.stdout.strip().splitlines()[-1], env, firma)


def _desplegar(slug: str, eid: str, conf: dict, repo: Path, pr: str, env: dict | None = None, firma: str = "") -> str:
    """Con capacidades.publicacion.desplegar («script {pr}», en las extensiones de la web) lanza el despliegue."""
    resultado = f"PR {pr}"
    if not conf.get("desplegar"):
        return resultado
    numero = pr.rstrip("/").rsplit("/", 1)[-1]
    if not numero.isdigit():
        raise Rechazo(f"No entiendo el número del PR: {pr}")
    partes = conf["desplegar"].replace("{pr}", numero).split()
    ruta = (C.carpeta(slug) / "extensiones" / partes[0]).resolve()
    if not str(ruta).startswith(str((C.carpeta(slug) / "extensiones").resolve())) or not ruta.exists():
        raise Rechazo(f"PR {pr}, pero no encuentro el script de despliegue {partes[0]} en las extensiones")
    if env is None:
        s = C.secretos(slug)
        env = {**os.environ, **({"GH_TOKEN": s["GH_TOKEN"]} if s.get("GH_TOKEN") else {})}
    env = {**env, "HSEO_FIRMA": firma, "HSEO_ENCARGO": eid}   # quién aprobó: el script decide
    # el commit que la persona vio al aprobar: el script de la web debe negarse si el PR ya no está en ese commit
    aprobado = next((((x.get("correo") or {}).get("huella") or {}).get("pr") for x in _cargar("hseo_puertas").puertas(("decidida",))
                     if x.get("encargo") == eid and x.get("cliente") == slug), None)
    if aprobado:
        env["HSEO_PR_SHA"] = aprobado
    (C.carpeta(slug) / "logs").mkdir(parents=True, exist_ok=True)
    subprocess.Popen(B.desacoplar(["bash", str(ruta), *partes[1:]]), start_new_session=True, cwd=str(repo), env=env,
                     stdout=open(C.carpeta(slug) / "logs" / f"desplegar-{eid}.log", "w"), stderr=subprocess.STDOUT)
    return resultado + " · despliegue lanzado"


def estado_despliegue(slug: str, eid: str, max_horas: float = 2.0) -> dict | None:
    """Cómo terminó el despliegue lanzado al publicar (logs/desplegar-<encargo>.log). None mientras sigue.
    {"ok": bool, "liga": bool, "texto": str}. Lee la última línea: DESPLIEGUE_OK | DESPLIEGUE_FALLO | DESPLIEGUE_MODO_LIGA."""
    log = C.carpeta(slug) / "logs" / f"desplegar-{eid}.log"
    if not log.exists():
        return None
    lineas = [l.strip() for l in log.read_text(errors="replace").splitlines() if l.strip()]
    ultima = lineas[-1] if lineas else ""
    hecho = next((l for l in reversed(lineas) if l.startswith("OK publicado")), "")
    errores = [l for l in lineas if l.startswith(("ERROR", "⚠️"))][-3:]
    if ultima.startswith("DESPLIEGUE_OK"):
        return {"ok": True, "liga": False, "texto": hecho or "Publicado."}
    if ultima.startswith("DESPLIEGUE_MODO_LIGA"):
        return {"ok": False, "liga": True, "texto": "No se publicó: hay partido (la web está en el espejo del modo liga)."}
    if ultima.startswith("DESPLIEGUE_FALLO") or (errores and not ultima.startswith(("OK", ">>"))):
        return {"ok": False, "liga": False, "texto": "\n".join(errores) or ultima}
    if time.time() - log.stat().st_mtime > max_horas * 3600:
        return {"ok": False, "liga": False, "texto": f"El despliegue no dice nada desde hace más de {max_horas:g} h: {ultima[:200]}"}
    return None


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


def _plantilla_args(plantilla: dict, valores: dict) -> dict:
    """{"titulo": "{titulo}", "publicar": true} → argumentos. «{x}» entero toma el valor tal cual (número, booleano);
    si no hay valor, la clave se omite. Texto con {x} dentro se rellena como texto."""
    out = {}
    for k, v in plantilla.items():
        if isinstance(v, str):
            m = re.fullmatch(r"{(\w+)}", v)
            if m:
                if valores.get(m.group(1)) not in (None, ""):
                    out[k] = valores[m.group(1)]
                continue
            out[k] = re.sub(r"{(\w+)}", lambda x: str(valores.get(x.group(1), "")), v)
        else:
            out[k] = v
    return out


def _idioma(pub: dict, cfg: dict) -> str:
    if pub.get("idioma"):
        return str(pub["idioma"])
    url = str(pub.get("url") or "")
    for i in cfg.get("idiomas") or []:
        if f"/{i}/" in url:
            return i
    return str(cfg.get("idioma") or "es")


def mcp(slug: str, eid: str, cfg: dict, pub: dict, meta: dict, cuerpo: str, firma: str) -> str:
    """Artículo (y sus traducciones) por el servidor MCP de la web. capacidades.publicacion:
    {url, guardar: {herramienta, args: {…plantilla con {titulo} {slug} {cuerpo} {idioma} {traduccion_de}…}}, id: campo
    del resultado con el número de la pieza (id), url_resultado: campo con su dirección (url)}. Las traducciones vienen
    en publicacion.json → traducciones: [{idioma, contenido, titulo, meta_descripcion, slug}] y se guardan enlazadas."""
    conf = cfg["capacidades"]["publicacion"]
    if pub.get("tipo") == "cambio-tecnico":
        if _solo_seo(conf, pub):
            return seo_mcp(slug, eid, cfg, conf, pub)
        return entrega(slug, eid, cfg, pub, meta, cuerpo, firma) + (
            " (por MCP solo se publican artículos y, con capacidades.publicacion.seo, títulos y metas: lo demás, a mano)")
    g = conf.get("guardar") or {}
    if not g.get("herramienta") or not isinstance(g.get("args"), dict):
        raise Rechazo("Falta capacidades.publicacion.guardar (herramienta y args) para publicar por MCP")
    X = _cargar("hseo_mcp")
    campo_id, campo_url = conf.get("id", "id"), conf.get("url_resultado", "url")
    d = E.carpeta(slug, eid)

    def guardar(p: dict, m: dict, texto: str, original=None) -> dict:
        valores = {**m, **{k: v for k, v in p.items() if isinstance(v, (str, int, float, bool))},
                   "cuerpo": texto.strip(), "slug": slug_de(p, m), "idioma": _idioma(p, cfg),
                   "titulo": p.get("titulo") or m.get("titulo") or m.get("title", ""),
                   "meta_descripcion": p.get("meta_descripcion") or m.get("meta_descripcion") or m.get("description", ""),
                   "traduccion_de": original}
        return X.llamar(slug, g["herramienta"], _plantilla_args(g["args"], valores), escribir=True)

    hechos, avisos = [], []
    r = guardar(pub, meta, cuerpo)
    hechos.append(f"{_idioma(pub, cfg)}: {r.get(campo_url) or r.get(campo_id)}")
    avisos += [str(w) for w in r.get("warnings") or []]
    original = r.get(campo_id)
    for t in pub.get("traducciones") or []:
        f = (d / str(t.get("contenido") or "")).resolve()
        if not str(f).startswith(str(d.resolve())) or not f.is_file():
            raise Rechazo(f"Publicada la versión principal ({hechos[0]}), pero no encuentro la traducción {t.get('contenido')}")
        tm, tc = separar_cabecera(f.read_text())
        rt = guardar(t, tm, tc, original)
        hechos.append(f"{_idioma(t, cfg)}: {rt.get(campo_url) or rt.get(campo_id)}")
        avisos += [str(w) for w in rt.get("warnings") or []]
    B.escribir(d / "publicado.json", {"principal": original, "hechos": hechos, "ts": B.ahora()})   # para deshacer después
    return "MCP " + " · ".join(hechos) + (f" · avisos de la web: {'; '.join(avisos)[:300]}" if avisos else "")


# ── solo el SEO de páginas ya publicadas, por MCP (títulos y metas; nunca el texto ni el estado) ──────────────────────
# capacidades.publicacion.seo: {"colecciones": {"/articulos/": "posts", "/sintomas/": "sintomas"},
#                               "leer": "content_get", "actualizar": "content_update"}
# Forma de las herramientas de contenido de EmDash: leer {collection, id} → {item: {id, status, seo: {title,
# description…}}, _rev}; actualizar {collection, id, _rev, seo: {…}} cambia solo el SEO de la versión publicada (no
# crea borrador ni toca los de la autora). Todo o nada: si una página falla, se devuelven las ya cambiadas.
SEO_CAMPOS = {"titulo": "title", "title": "title", "titulo-seo": "title", "titulo_seo": "title",
              "meta": "description", "meta-descripcion": "description", "meta_descripcion": "description",
              "description": "description"}


def _solo_seo(conf: dict, pub: dict) -> bool:
    cambios = pub.get("cambios") or []
    return (isinstance(conf.get("seo"), dict) and bool(cambios)
            and all(str(c.get("accion", "")).strip().lower() in SEO_CAMPOS and c.get("url") and str(c.get("despues") or "").strip()
                    for c in cambios))


def _pieza_seo(cfg: dict, s: dict, url: str) -> tuple:
    """URL → (colección, slug) según capacidades.publicacion.seo.colecciones (prefijo de ruta más largo)."""
    dom = str(cfg.get("dominio", "")).lower().removeprefix("www.")
    host = (urllib.parse.urlsplit(url).hostname or "").lower().removeprefix("www.")
    if not host or not host.endswith(dom):
        raise Rechazo(f"No es de {dom}: {url}")
    ruta = _ruta(url) + "/"
    for pre in sorted(s.get("colecciones") or {}, key=len, reverse=True):
        p = "/" + pre.strip("/") + "/" if pre.strip("/") else "/"
        resto = ruta[len(p):].strip("/") if ruta.startswith(p) else ""
        if resto and "/" not in resto:
            return s["colecciones"][pre], resto
    raise Rechazo(f"No sé en qué colección está {url} (capacidades.publicacion.seo.colecciones)")


def _comprobar_en_web(url: str, campo: str, valor: str) -> bool | None:
    """¿La página publicada ya muestra el valor? None si no se pudo mirar."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "hermes-seo/0.1", "Cache-Control": "no-cache"})
        with urllib.request.urlopen(req, timeout=20) as r:
            h = html.unescape(r.read(600_000).decode("utf-8", "replace"))
    except Exception:   # noqa: BLE001  comprobar nunca frena
        return None
    if campo == "title":
        m = re.search(r"<title[^>]*>(.*?)</title>", h, re.S | re.I)
        return bool(m) and valor.strip() in m.group(1)
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]*>', h, re.I)
    return bool(m) and valor.strip() in m.group(0)


def seo_mcp(slug: str, eid: str, cfg: dict, conf: dict, pub: dict) -> str:
    s, X = conf["seo"], _cargar("hseo_mcp")
    leer, actualizar = s.get("leer", "content_get"), s.get("actualizar", "content_update")
    # 1. Agrupar por página y leer cada una antes de tocar nada (si algo no cuadra, no se cambia ninguna)
    paginas: dict = {}
    for c in pub.get("cambios") or []:
        col, sl = _pieza_seo(cfg, s, c["url"])
        p = paginas.setdefault((col, sl), {"url": c["url"], "coleccion": col, "slug": sl, "despues": {}})
        p["despues"][SEO_CAMPOS[str(c["accion"]).strip().lower()]] = str(c["despues"]).strip()
    for p in paginas.values():
        r = X.llamar(slug, leer, {"collection": p["coleccion"], "id": p["slug"]})
        item = (r or {}).get("item") or {}
        if not item.get("id") or not r.get("_rev"):
            raise Rechazo(f"La web no devolvió la página {p['url']} (ni se ha tocado nada)")
        if str(item.get("status", "")).lower() != "published":
            raise Rechazo(f"{p['url']} no está publicada: no se toca (ni se ha tocado nada)")
        p["id"], p["rev"] = item["id"], r["_rev"]
        p["antes"] = {k: (item.get("seo") or {}).get(k) for k in p["despues"]}

    def poner(p: dict, valores: dict, rev: str):
        return X.llamar(slug, actualizar, {"collection": p["coleccion"], "id": p["id"], "_rev": rev, "seo": valores}, escribir=True)

    # 2. Aplicar; si una falla, devolver las ya cambiadas a su valor anterior
    hechas = []
    for p in paginas.values():
        try:
            poner(p, p["despues"], p["rev"])
        except Rechazo as e:
            vueltas = []
            for h in hechas:
                try:
                    r = X.llamar(slug, leer, {"collection": h["coleccion"], "id": h["id"]})
                    poner(h, h["antes"], r["_rev"]); vueltas.append(h["url"])
                except Exception:   # noqa: BLE001
                    pass
            raise Rechazo(f"Falló {p['url']}: {e}. " + (f"Devueltas a como estaban: {', '.join(vueltas)}" if vueltas else "No se había cambiado ninguna")
                          + (f"; NO se pudieron devolver: {', '.join(h['url'] for h in hechas if h['url'] not in vueltas)}"
                             if len(vueltas) < len(hechas) else ""))
        hechas.append(p)
    # 3. Para deshacer: el valor anterior de cada campo (null = la web usaba el título/resumen de la página)
    d = E.carpeta(slug, eid)
    B.escribir(d / "publicado.json", {"seo": [{k: p[k] for k in ("url", "coleccion", "id", "antes", "despues")} for p in hechas],
                                      "deshacer": f"{actualizar} con seo = antes en cada página", "ts": B.ahora()})
    vistas = [_comprobar_en_web(p["url"], k, v) for p in hechas for k, v in p["despues"].items()]
    n_campos = len(vistas)
    nota = (f"comprobado en la web: {sum(1 for v in vistas if v)} de {n_campos}" if any(v is not None for v in vistas)
            else "sin comprobar en la web")
    return f"MCP SEO: {len(hechas)} página(s), {n_campos} campo(s) cambiados en vivo ({nota}); los anteriores quedan en publicado.json"


ADAPTADORES = {"repo-pr": repo_pr, "wordpress": wordpress, "entrega": entrega, "mcp": mcp}


# ── retirar lo publicado: igual para todas las webs; cada adaptador sabe cómo ─────────────────────────────────────
# La persona pide quitar páginas (`hseo retirar <web> <url>…`). Con MCP o WordPress se abre una puerta «retirar» y, al
# aprobarla, se despublican (quedan en borrador: se pueden volver a publicar en la web). Con repo y PR se lanza un
# cambio técnico, cuyo PR es la decisión. Sin forma de publicar, se dice que es a mano.
CON_PUERTA = ("mcp", "wordpress")


def _ruta(u) -> str:
    return (urllib.parse.urlsplit(str(u).strip()).path or "/").rstrip("/") or "/"


def _publicadas_mcp(slug: str, conf: dict) -> tuple:
    """(config de retirar, {ruta: pieza publicada}) leyendo la lista de la web con su herramienta de lectura."""
    r = conf.get("retirar") or {}
    if not r.get("buscar") or not r.get("herramienta"):
        raise Rechazo("Falta capacidades.publicacion.retirar (buscar, herramienta, args) para retirar por MCP")
    lista = _cargar("hseo_mcp").llamar(slug, r["buscar"], r.get("buscar_args") or {})
    items = lista.get(r.get("lista", "datos")) if isinstance(lista, dict) else lista
    cu, ce = r.get("url", "url"), r.get("estado", "status")
    return r, {_ruta(i[cu]): i for i in items or [] if isinstance(i, dict) and i.get(cu)
               and str(i.get(ce, "published")).lower() in ("published", "publish", "publicado")}


def _wp(slug: str, conf: dict):
    s = C.secretos(slug)
    if not s.get("WP_USUARIO") or not s.get("WP_APP_PASSWORD"):
        raise Rechazo("Faltan WP_USUARIO y WP_APP_PASSWORD en los secretos de la web")
    base, auth = conf["url_api"].rstrip("/"), base64.b64encode(f"{s['WP_USUARIO']}:{s['WP_APP_PASSWORD']}".encode()).decode()

    def pedir(metodo: str, ruta: str, datos=None):
        req = urllib.request.Request(f"{base}{ruta}", method=metodo, data=json.dumps(datos).encode() if datos is not None else None,
                                     headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json", "User-Agent": "hermes-seo/0.1"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read() or b"null")
        except urllib.error.HTTPError as e:
            raise Rechazo(f"WordPress respondió {e.code}: {e.read()[:200].decode(errors='replace')}")
    return pedir


def _publicadas_wp(slug: str, conf: dict, urls: list) -> tuple:
    pedir, tipo = _wp(slug, conf), conf.get("tipo", "posts")
    hallado = {}
    for u in urls:
        seg = _ruta(u).rsplit("/", 1)[-1]
        for i in pedir("GET", f"/{tipo}?slug={urllib.parse.quote(seg)}&status=publish&_fields=id,link") or []:
            if _ruta(i.get("link", "")) == _ruta(u):
                hallado[_ruta(u)] = i
    return pedir, hallado


def _comprobar_urls(cfg: dict, urls: list) -> list:
    urls = [str(u).strip() for u in urls if str(u).strip()]
    if not urls:
        raise Rechazo("Di qué páginas retirar (sus direcciones)")
    dom = str(cfg.get("dominio", "")).lower()
    ajenas = [u for u in urls if not (urllib.parse.urlsplit(u).hostname or "").lower().removeprefix("www.").endswith(dom.removeprefix("www."))]
    if ajenas:
        raise Rechazo(f"No son de {dom}: {', '.join(ajenas)}")
    return urls


def pedir_retirar(slug: str, urls: list, motivo: str = "", quien: str = "") -> str:
    """Lo que pide la persona: abre la puerta «retirar» (o el cambio técnico, si la web publica por PR)."""
    cfg = C.leer(slug)
    conf = cfg["capacidades"].get("publicacion") or {}
    ad = conf.get("adaptador", "ninguno")
    urls = _comprobar_urls(cfg, urls)
    PU = _cargar("hseo_puertas")
    if ad in CON_PUERTA:
        hallado = _publicadas_mcp(slug, conf)[1] if ad == "mcp" else _publicadas_wp(slug, conf, urls)[1]
        faltan = [u for u in urls if _ruta(u) not in hallado]
        if faltan:
            raise Rechazo(f"No están publicadas en la web: {', '.join(faltan)}")
        if any(p["cliente"] == slug and p["tipo"] == "retirar" and set(map(_ruta, p.get("hallazgos") or [])) & set(map(_ruta, urls))
               for p in PU.puertas()):
            raise Rechazo("Ya hay una puerta pendiente para retirar alguna de esas páginas")
        texto = ("Dejan de estar en la web (su dirección dirá que ya no existe y salen del mapa del sitio). No se borran: quedan en "
                 "borrador y se pueden volver a publicar desde la propia web.\n\n" + "\n".join(f"• {u}" for u in urls)
                 + (f"\n\nMotivo: {motivo}" if motivo else "") + (f"\nLo pidió: {quien}" if quien else ""))
        p = PU.abrir(slug, None, "retirar", f"{PU.EMOJI['retirar']} Retirar {len(urls)} página(s) · {cfg['nombre']}",
                     texto, hallazgos=urls, al_aprobar="retirar")
        return f"Puerta {p['id']} abierta: le llega a la persona para decidir"
    if ad == "repo-pr":
        n = E.lanzar(slug, "cambio-seo", {"que": "Retirar del sitio estas páginas (dejar de publicarlas sin romper enlaces "
                                                 f"internos, sitemap ni traducciones): {' '.join(urls)}" + (f". Motivo: {motivo}" if motivo else "")},
                     quien=quien or "retirar")
        return f"Lanzado {n['id']}: prepara el PR que las retira y llega a la persona como cualquier cambio técnico"
    raise Rechazo(f"{cfg['nombre']} no publica sola (adaptador «{ad}»): esas páginas hay que retirarlas a mano")


def retirar(slug: str, urls: list, firma: str) -> str:
    """Lo que hace el notario al aprobarse la puerta «retirar»: despublica cada página. Nada si falta alguna."""
    cfg = C.leer(slug)
    if (cfg.get("politicas") or {}).get("pausado") or (B.home() / "pausa").exists():
        raise Rechazo(f"{cfg['nombre']} está en pausa: no se toca la web")
    conf = cfg["capacidades"].get("publicacion") or {}
    ad = conf.get("adaptador", "ninguno")
    urls = _comprobar_urls(cfg, urls)
    _antes_de_publicar(slug, cfg)
    hechos = []
    if ad == "mcp":
        r, hallado = _publicadas_mcp(slug, conf)
        faltan = [u for u in urls if _ruta(u) not in hallado]
        if faltan:
            raise Rechazo(f"Ya no están publicadas (no se ha tocado nada): {', '.join(faltan)}")
        X = _cargar("hseo_mcp")
        for u in urls:
            try:
                X.llamar(slug, r["herramienta"], _plantilla_args(r.get("args") or {"id": "{id}"}, {"id": hallado[_ruta(u)][r.get("id", "id")]}),
                         escribir=True)
            except Rechazo as e:
                raise Rechazo(f"Retiradas {', '.join(hechos) or 'ninguna'}; falló {_ruta(u)}: {e}")
            hechos.append(_ruta(u))
    elif ad == "wordpress":
        pedir, hallado = _publicadas_wp(slug, conf, urls)
        faltan = [u for u in urls if _ruta(u) not in hallado]
        if faltan:
            raise Rechazo(f"Ya no están publicadas (no se ha tocado nada): {', '.join(faltan)}")
        for u in urls:
            pedir("POST", f"/{conf.get('tipo', 'posts')}/{hallado[_ruta(u)]['id']}", {"status": "draft"})
            hechos.append(_ruta(u))
    else:
        raise Rechazo(f"{cfg['nombre']} no retira páginas por puerta (adaptador «{ad}»)")
    B.anotar(C.carpeta(slug) / "cambios.jsonl", {"id": f"r-{int(time.time())}", "ts": B.ahora(), "clase": "retirada",
                                                 "hipotesis": "", "urls": urls, "adaptador": ad, "resultado": ", ".join(hechos), "firma": firma})
    try:
        _cargar("hseo_wiki").regenerar_cambios(slug)
    except Exception:   # noqa: BLE001  la memoria nunca frena
        pass
    return "retiradas: " + ", ".join(hechos)


# ── worktrees: que no se coman el disco ──────────────────────────────────────────────────────────────────────────────
def _worktree(slug: str, eid: str) -> tuple:
    """(repo, carpeta del worktree del encargo) según publicacion.worktrees (o <cliente>/wt), o (None, None)."""
    conf = (C.leer(slug).get("capacidades") or {}).get("publicacion") or {}
    if not conf.get("repo"):
        return None, None
    base = Path(os.path.expanduser(str(conf.get("worktrees") or C.carpeta(slug) / "wt")))
    wt = base / eid
    return Path(os.path.expanduser(conf["repo"])), (wt if (wt / ".git").exists() else None)


def aligerar(slug: str, eid: str) -> list:
    """Mientras la puerta espera, borra lo regenerable del worktree (publicacion.regenerables, p. ej. node_modules).
    Si hay que rehacer, la etapa lo vuelve a instalar. Devuelve lo borrado."""
    conf = (C.leer(slug).get("capacidades") or {}).get("publicacion") or {}
    _, wt = _worktree(slug, eid)
    borrado = []
    for nombre in conf.get("regenerables") or []:
        if not nombre or "/" in nombre or nombre.startswith("."):
            continue
        d = wt / nombre if wt else None
        if d and d.is_dir() and not d.is_symlink():
            shutil.rmtree(d, ignore_errors=True)
            borrado.append(nombre)
    return borrado


def limpiar_worktree(slug: str, eid: str, publicado: bool = False) -> str:
    """Al cerrarse el encargo, quita su worktree si no pierde nada: sin cambios sin guardar y con el último commit
    ya en el remoto (la rama sigue en GitHub). Con `publicado` (el despliegue terminó bien y el PR está fusionado)
    no se mira el remoto, porque al fusionar la rama puede haberse borrado o reescrito, y se borra también la rama
    local. Es igual para todas las webs: no depende de que el script de despliegue de cada una lo haga."""
    repo, wt = _worktree(slug, eid)
    if not wt:
        return ""
    try:
        if _git(wt, "status", "--porcelain").strip():
            return f"no se quita {wt}: tiene cambios sin guardar"
        if not publicado:
            _git(repo, "fetch", "-q", "origin")
            if not _git(wt, "branch", "-r", "--contains", "HEAD").strip():
                return f"no se quita {wt}: tiene commits que no están en el remoto"
        rama = _git(wt, "symbolic-ref", "-q", "--short", "HEAD").strip() if publicado else ""
        _git(repo, "worktree", "remove", "--force", str(wt))
        _git(repo, "worktree", "prune")
        if rama.startswith("hermes/"):
            try:
                _git(repo, "branch", "-D", rama)
            except Exception:   # noqa: BLE001  la rama local es lo de menos
                pass
        return f"quitado {wt}"
    except Exception as e:   # nunca debe romper el cierre de una puerta
        return f"no se quitó {wt}: {e}"


def publicar(slug: str, eid: str, firma: str) -> str:
    cfg = C.leer(slug)
    ad = (cfg["capacidades"].get("publicacion") or {}).get("adaptador", "ninguno")
    if ad not in ADAPTADORES:
        raise Rechazo(f"{cfg['nombre']} no tiene configurado cómo publicar (capacidades.publicacion.adaptador)")
    if (cfg.get("politicas") or {}).get("pausado") or (B.home() / "pausa").exists():
        raise Rechazo(f"{cfg['nombre']} está en pausa: no se publica")
    _antes_de_publicar(slug, cfg)
    pub, meta, cuerpo = _leer_publicacion(slug, eid)
    if pub.get("tipo") != "cambio-tecnico" and not pub.get("pr") and not cuerpo.strip():
        raise Rechazo("El contenido está vacío")
    resultado = ADAPTADORES[ad](slug, eid, cfg, pub, meta, cuerpo, firma)
    _anotar_cambio(slug, eid, pub, ad, resultado, firma)
    return resultado
