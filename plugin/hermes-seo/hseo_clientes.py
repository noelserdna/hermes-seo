"""Clientes de hermes-seo: cada web es un cliente con su carpeta en HERMES_SEO_HOME/clientes/<slug>/.

  cliente.json    configuración (plantillas/cliente.json), validada antes de cada escritura
  secretos.env    claves del cliente (600); nunca se vuelcan en ninguna salida
  wiki/           memoria del cliente (llm-wiki, git propio)
  datos/          fotos diarias y metricas.db
  informes/ briefs/ logs/ wt/ extensiones/
  config.jsonl    historial de cambios de configuración (quién, qué, antes, después)

CLI:
  hseo_clientes.py alta <slug> <dominio> [--estado nueva|repo|wordpress|sin-acceso] [--nombre N]
  hseo_clientes.py listar [--json]
  hseo_clientes.py ver <slug>
  hseo_clientes.py config <slug> <clave.con.puntos> <valor>   (valor JSON o texto)
  hseo_clientes.py capacidades <slug>
  hseo_clientes.py validar <slug>
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import re
import sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent


def _cargar(nombre: str):
    """Módulos hermanos sin paquete instalable (Hermes carga el plugin desde su carpeta)."""
    if nombre in sys.modules:
        return sys.modules[nombre]
    spec = importlib.util.spec_from_file_location(nombre, AQUI / f"{nombre}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nombre] = mod
    spec.loader.exec_module(mod)
    return mod


B = _cargar("hseo_base")
Rechazo = B.Rechazo

ESTADOS_WEB = ("nueva", "repo", "wordpress", "sin-acceso")
PUBLICACION = ("ninguno", "repo-pr", "wordpress", "entrega")
ANALITICA = ("ninguna", "cloudflare", "ga4", "plausible")
# qué adaptadores de publicación tienen sentido en cada estado de la web («ninguno»: aún sin configurar, se puede
# medir y auditar pero no publicar)
PUBLICACION_POR_ESTADO = {"nueva": {"ninguno", "repo-pr", "wordpress", "entrega"},
                          "repo": {"ninguno", "repo-pr", "entrega"},
                          "wordpress": {"ninguno", "wordpress", "entrega"}, "sin-acceso": {"ninguno", "entrega"}}
DOMINIO = re.compile(r"^(?=.{4,253}$)([a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$")
SUBCARPETAS = ("wiki", "datos", "informes", "briefs", "logs", "wt", "extensiones")


def plantilla() -> dict:
    raiz = AQUI.parent.parent   # repo/plugin/hermes-seo → repo; instalado: actual/plugin/hermes-seo → actual
    for p in (raiz / "plantillas" / "cliente.json", B.home() / "actual" / "plantillas" / "cliente.json", AQUI / "cliente.json"):
        if p.exists():
            return json.loads(p.read_text())
    raise Rechazo("No encuentro la plantilla del cliente (plantillas/cliente.json)")


def carpeta(slug: str) -> Path:
    return B.home() / "clientes" / B.validar_slug(slug)


def listar() -> list:
    d = B.home() / "clientes"
    return sorted(p.parent.name for p in d.glob("*/cliente.json")) if d.is_dir() else []


def leer(slug: str) -> dict:
    cfg = B.leer(carpeta(slug) / "cliente.json")
    if not cfg:
        raise Rechazo(f"No conozco el cliente «{slug}». Clientes: {', '.join(listar()) or 'ninguno'}")
    return cfg


def _zona_valida(z: str) -> bool:
    try:
        from zoneinfo import ZoneInfo
        ZoneInfo(z)
        return True
    except Exception:
        return False


def validar(cfg: dict) -> list:
    """Lista de errores (en castellano, para la persona); vacía si la configuración es coherente."""
    e = []
    try:
        B.validar_slug(cfg.get("slug", ""))
    except Rechazo as x:
        e.append(str(x))
    if not DOMINIO.match(str(cfg.get("dominio", ""))):
        e.append("dominio: escribe solo el dominio, sin https:// ni barras (p. ej. ejemplo.com)")
    if not str(cfg.get("url", "")).startswith("https://"):
        e.append("url: tiene que empezar por https://")
    if not re.fullmatch(r"[a-z]{2}", str(cfg.get("idioma", ""))):
        e.append("idioma: código de 2 letras (es, en…)")
    mercados = cfg.get("mercados")
    if not isinstance(mercados, list) or not mercados:
        e.append("mercados: al menos uno, p. ej. [{\"pais\": \"ES\", \"bing\": \"es-ES\"}]")
    else:
        for m in mercados:
            if not (isinstance(m, dict) and re.fullmatch(r"[A-Z]{2}", str(m.get("pais", "")))
                    and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", str(m.get("bing", "")))):
                e.append(f"mercados: {m} no tiene la forma {{\"pais\": \"ES\", \"bing\": \"es-ES\"}}")
    if not _zona_valida(str(cfg.get("zona_horaria", ""))):
        e.append("zona_horaria: no la reconozco (p. ej. Europe/Madrid)")
    estado = cfg.get("estado_web")
    if estado not in ESTADOS_WEB:
        e.append(f"estado_web: uno de {', '.join(ESTADOS_WEB)}")
    cap = cfg.get("capacidades") or {}
    pub = cap.get("publicacion") or {}
    ad = pub.get("adaptador")
    if ad not in PUBLICACION:
        e.append(f"capacidades.publicacion.adaptador: uno de {', '.join(PUBLICACION)}")
    elif estado in PUBLICACION_POR_ESTADO and ad not in PUBLICACION_POR_ESTADO[estado]:
        e.append(f"capacidades.publicacion.adaptador «{ad}» no encaja con una web «{estado}» "
                 f"(admite: {', '.join(sorted(PUBLICACION_POR_ESTADO[estado]))})")
    if ad == "repo-pr" and not pub.get("repo"):
        e.append("capacidades.publicacion.repo: la ruta del repo de la web (para publicar por PR)")
    if ad == "wordpress" and not str(pub.get("url_api", "")).startswith("https://"):
        e.append("capacidades.publicacion.url_api: la dirección https de la API de WordPress")
    if (cap.get("analitica") or {}).get("adaptador") not in ANALITICA:
        e.append(f"capacidades.analitica.adaptador: uno de {', '.join(ANALITICA)}")
    if not isinstance(cap.get("difusion", []), list):
        e.append("capacidades.difusion: una lista")
    pol = cfg.get("politicas") or {}
    if not isinstance(pol.get("pausado", False), bool):
        e.append("politicas.pausado: true o false")
    if pol.get("congelado_hasta") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(pol["congelado_hasta"])):
        e.append("politicas.congelado_hasta: fecha AAAA-MM-DD o vacío")
    if not isinstance(pol.get("tope_semanal", 0), int) or pol.get("tope_semanal", 0) < 0:
        e.append("politicas.tope_semanal: un número entero (0 = sin tope)")
    if not isinstance((cfg.get("jev") or {}).get("permitido", True), bool):
        e.append("jev.permitido: true o false")
    for k in ("modelos", "ejecutores", "crons"):
        if not isinstance(cfg.get(k, {}), dict):
            e.append(f"{k}: un objeto")
    return e


def capacidades(cfg: dict) -> set:
    """Lo que el cliente permite hacer. Las etapas de las pipelines declaran lo que necesitan (`requiere`)."""
    c = set()
    cap = cfg.get("capacidades") or {}
    ad = (cap.get("publicacion") or {}).get("adaptador", "ninguno")
    if ad != "ninguno":
        c |= {"publicacion", f"publicacion:{ad}"}
    if ad == "repo-pr":
        c.add("repo")
    bus = cap.get("busqueda") or {}
    if bus.get("gsc"):
        c.add("gsc")
    if bus.get("bing"):
        c.add("bing")
    an = (cap.get("analitica") or {}).get("adaptador", "ninguna")
    if an != "ninguna":
        c |= {"analitica", f"analitica:{an}"}
    for d in cap.get("difusion") or []:
        c.add(f"difusion:{d}")
    if cfg.get("competidores"):
        c.add("competidores")
    if (cfg.get("jev") or {}).get("permitido", True):
        c.add("jev")
    return c


def _guardar(slug: str, cfg: dict) -> None:
    errores = validar(cfg)
    if errores:
        raise Rechazo("La configuración no es válida:\n- " + "\n- ".join(errores))
    B.escribir(carpeta(slug) / "cliente.json", cfg)


def alta(slug: str, dominio: str, estado_web: str = "nueva", nombre: str = "", quien: str = "") -> dict:
    """Crea el cliente con la plantilla. No lanza nada: eso lo hace la pipeline «alta»."""
    B.validar_slug(slug)
    dominio = dominio.strip().lower().removeprefix("https://").removeprefix("http://").strip("/")
    d = carpeta(slug)
    with B.cerrojo("clientes"):
        if (d / "cliente.json").exists():
            raise Rechazo(f"El cliente «{slug}» ya existe")
        cfg = plantilla()
        cfg.update(slug=slug, nombre=nombre or slug, dominio=dominio, url=f"https://{dominio}", estado_web=estado_web)
        # adaptador de publicación por defecto según el estado (se cambia luego con config)
        cfg["capacidades"]["publicacion"]["adaptador"] = {"sin-acceso": "entrega"}.get(estado_web, "ninguno")
        _guardar(slug, cfg)
        for s in SUBCARPETAS:
            (d / s).mkdir(parents=True, exist_ok=True)
        sec = d / "secretos.env"
        if not sec.exists():
            sec.write_text("# Claves de este cliente (KEY=valor). Solo las lee el plugin; nunca se muestran.\n")
        os.chmod(sec, 0o600)
        B.anotar(d / "config.jsonl", {"ts": B.ahora(), "quien": quien, "accion": "alta", "estado_web": estado_web})
    return cfg


def _poner(cfg: dict, clave: str, valor) -> tuple:
    partes = clave.split(".")
    if not all(re.fullmatch(r"[a-z_][a-z0-9_-]*", p) for p in partes):
        raise Rechazo(f"Clave no válida: {clave}")
    if partes[0] in ("slug", "version"):
        raise Rechazo(f"«{partes[0]}» no se cambia")
    nodo = cfg
    for p in partes[:-1]:
        if not isinstance(nodo.get(p), dict):
            if p in nodo:
                raise Rechazo(f"«{p}» no es un objeto")
            nodo[p] = {}
        nodo = nodo[p]
    antes = copy.deepcopy(nodo.get(partes[-1]))
    nodo[partes[-1]] = valor
    return antes, valor


def config(slug: str, clave: str, valor, quien: str = "") -> dict:
    """Cambia un valor (clave con puntos) validando la configuración completa antes de escribir."""
    if isinstance(valor, str):
        try:
            valor = json.loads(valor)
        except ValueError:
            pass   # texto
    with B.cerrojo("clientes"):
        cfg = leer(slug)
        antes, despues = _poner(cfg, clave, valor)
        if clave == "dominio":
            cfg["url"] = f"https://{cfg['dominio']}"
        _guardar(slug, cfg)
        B.anotar(carpeta(slug) / "config.jsonl",
                 {"ts": B.ahora(), "quien": quien, "accion": "config", "clave": clave, "antes": antes, "despues": despues})
    return cfg


def secretos(slug: str) -> dict:
    """Claves del cliente más las globales (las del cliente mandan). Solo para pasarlas a procesos; nunca se imprimen."""
    def leer_env(p: Path) -> dict:
        out = {}
        try:
            for linea in p.read_text().splitlines():
                linea = linea.strip()
                if linea and not linea.startswith("#") and "=" in linea:
                    k, v = linea.split("=", 1)
                    out[k.strip()] = v.strip().strip('"').strip("'")
        except OSError:
            pass
        return out
    return {**leer_env(B.home() / "secretos.env"), **leer_env(carpeta(slug) / "secretos.env")}


def resumen(cfg: dict) -> str:
    cap = sorted(capacidades(cfg))
    pol = cfg.get("politicas") or {}
    extra = []
    if pol.get("pausado"):
        extra.append("⏸ en pausa")
    if pol.get("congelado_hasta"):
        extra.append(f"🧊 sin piezas nuevas hasta {pol['congelado_hasta']}")
    return (f"{cfg['nombre']} ({cfg['dominio']}) · web {cfg['estado_web']} · "
            f"publica: {(cfg['capacidades']['publicacion'] or {}).get('adaptador')}"
            + (f" · {' · '.join(extra)}" if extra else "") + f"\n  capacidades: {', '.join(cap) or 'ninguna'}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hseo_clientes.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("alta"); a.add_argument("slug"); a.add_argument("dominio")
    a.add_argument("--estado", default="nueva", choices=ESTADOS_WEB); a.add_argument("--nombre", default="")
    a.add_argument("--quien", default="")
    l = sub.add_parser("listar"); l.add_argument("--json", action="store_true")
    for n in ("ver", "capacidades", "validar"):
        sub.add_parser(n).add_argument("slug")
    c = sub.add_parser("config"); c.add_argument("slug"); c.add_argument("clave"); c.add_argument("valor")
    c.add_argument("--quien", default="")
    x = ap.parse_args(argv)
    try:
        if x.cmd == "alta":
            print(resumen(alta(x.slug, x.dominio, x.estado, x.nombre, x.quien)))
        elif x.cmd == "listar":
            cs = listar()
            if x.json:
                print(json.dumps([leer(s) for s in cs], ensure_ascii=False))
            else:
                print("\n".join(resumen(leer(s)) for s in cs) or "Sin clientes todavía.")
        elif x.cmd == "ver":
            print(json.dumps(leer(x.slug), ensure_ascii=False, indent=2))
        elif x.cmd == "capacidades":
            print(" ".join(sorted(capacidades(leer(x.slug)))))
        elif x.cmd == "validar":
            err = validar(leer(x.slug))
            print("ok" if not err else "\n".join(err))
            return 1 if err else 0
        elif x.cmd == "config":
            print(resumen(config(x.slug, x.clave, x.valor, x.quien)))
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
