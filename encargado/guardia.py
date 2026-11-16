"""Guardia de la COORDINADORA y de los ENCARGADOS de hermes-seo (hook pre_tool_call de Hermes, fail-closed).
Copiado y adaptado de hermes-sdd (encargado/guardia.py).

  python3 -I guardia.py <ámbito> <arnés>       (lee el evento de stdin)
    ámbito = cartera   la coordinadora (perfil default): todas las webs
    ámbito = <slug>    el encargado de una web (perfil seo-p-<slug>): solo esa

Tres niveles para mover el sistema, todos por la CLI `hseo` (nunca por otra vía):
  · sola            consultar, lanzar pipelines, reintentar una vez       → se permite
  · con aprobación  alta, config, pausar, modelos, excepciones y      → {"action":"approve"}: Hermes pregunta a
                    pipelines con coste externo                              la persona; en un cron no hay nadie y se deniega
  · nunca           decidir o firmar puertas, publicar, secretos,          → bloqueado (y la CLI ni siquiera lo ofrece)
                    aprobadores, código del arnés, configuración de Hermes
Además: ficheros solo en su wiki (y briefs/); terminal con una lista blanca de lectura; sin execute_code.

Bloquear = imprimir {"decision":"block","reason":…} y salir con 2 (dialecto de Hermes). Permitir = salir con 0.
"""
from __future__ import annotations

import glob
import json
import os
import re
import shlex
import sys

AMBITO = sys.argv[1]
ARNES = os.path.realpath(sys.argv[2])
ARNES_RUTAS = {ARNES, os.path.abspath(os.path.expanduser(sys.argv[2]))}
HSEO = os.path.realpath(os.environ.get("HERMES_SEO_HOME") or os.path.expanduser("~/.hermes/hermes-seo"))
HOME = os.path.expanduser("~")
CARTERA = AMBITO == "cartera"
CLIENTES = os.path.join(HSEO, "clientes")
APROBAR: list = []

# rutas de escritura
if CARTERA:
    ESCRIBE = [os.path.join(HSEO, "wiki")] + [os.path.join(CLIENTES, s, d) for s in os.listdir(CLIENTES)
                                               for d in ("wiki", "briefs")] if os.path.isdir(CLIENTES) else [os.path.join(HSEO, "wiki")]
else:
    ESCRIBE = [os.path.join(CLIENTES, AMBITO, "wiki"), os.path.join(CLIENTES, AMBITO, "briefs")]
SECRETOS = re.compile(r"(secretos\.env|aprobadores\.json|seo\.json|auth\.json|mcp-tokens|\.env\b|"
                      r"\.ssh|id_(rsa|ed25519)|\.pem\b|cuota\.json)")

LECTURA = {"ls", "cat", "head", "tail", "grep", "egrep", "rg", "wc", "jq", "sort", "uniq", "cut", "tr", "diff", "tree",
           "file", "stat", "date", "echo", "printf", "pwd", "basename", "dirname", "realpath", "column", "nl", "true",
           "cd", "test", "[", "shasum", "sha256sum", "md5sum", "dig", "host", "whois"}
GIT_LECTURA = {"log", "show", "diff", "status", "blame", "describe", "rev-parse", "ls-files", "shortlog", "grep"}
HSEO_SOLA = {"novedad", "mejora", "cuaderno", "ia", "aterrizaje", "gestion", "tanda", "wiki", "preguntar", "ordenar", "vueltas", "vigilancia", "parte", "propuesta", "clientes", "estado", "encargos", "encargo", "puertas", "puerta", "pipelines", "plan", "lanzar", "reintentar",
             "leccion", "lecciones", "datos", "preguntas", "mcp"}
HSEO_APROBAR = {"alta", "config", "pausar", "reanudar", "modelos", "contacto", "correo"}
# El encargado (que puede recibir texto de terceros: webs, correos) solo usa estas herramientas; cualquier otra se
# bloquea (el hook va con matcher ".*"). La coordinadora no tiene esta lista: es «ojos y manos en todo».
HERRAMIENTAS_ENCARGADO = {"terminal", "read_file", "write_file", "patch", "search_files", "skills_list", "skill_view",
                          "todo_list", "memory", "session_search", "clarify", "vision_analyze"}
CON_VALOR = {"--param", "--brief", "--cliente", "--dias", "--quien"}   # opciones de hseo que llevan un valor detrás


def bloquear(motivo: str) -> None:
    quien = "la coordinadora" if CARTERA else f"el encargado de {AMBITO}"
    print(json.dumps({"decision": "block", "reason": f"hermes-seo ({quien}): {motivo}. Para mover el sistema usa la CLI "
                      "hseo; decidir puertas y publicar es de la persona: explícale qué harías."},
                     ensure_ascii=False))
    sys.exit(2)


def ruta(p: str, base: str) -> str:
    p = os.path.expanduser(p)
    return os.path.realpath(p if os.path.isabs(p) else os.path.join(base, p))


def dentro(p: str, d: str) -> bool:
    return p == d or p.startswith(d.rstrip(os.sep) + os.sep)


def con_coste(pipeline: str, cliente: str) -> bool:
    for f in [os.path.join(ARNES, "pipelines", f"{pipeline}.json"),
              os.path.join(CLIENTES, cliente, "extensiones", "pipelines", f"{pipeline}.json")]:
        try:
            if json.load(open(f)).get("coste_externo"):
                return True
        except (OSError, ValueError):
            pass
    return False


def es_hseo(seg: list, cwd: str) -> list | None:
    """Los argumentos de hseo si el segmento es la CLI del arnés (hseo, bash <arnés>/hseo, <arnés>/hseo)."""
    if seg[0] == "hseo":
        return seg[1:]
    if os.path.basename(seg[0]) == "hseo" and dentro(ruta(seg[0], cwd), ARNES):
        return seg[1:]
    if seg[0] in ("bash", "sh") and len(seg) > 1 and os.path.basename(seg[1]) == "hseo" and dentro(ruta(seg[1], cwd), ARNES):
        return seg[2:]
    return None


def cliente_de(args: list) -> str | None:
    """El cliente sobre el que actúa una orden de hseo (None si es global)."""
    sub, resto = args[0], args[1:]
    if "--cliente" in resto:
        i = resto.index("--cliente")
        return resto[i + 1] if i + 1 < len(resto) else None
    pos, saltar = [], False
    for a in resto:   # posicionales de verdad: sin las opciones ni sus valores («--brief web otra» no engaña)
        if saltar:
            saltar = False
            continue
        if a.startswith("--"):
            saltar = a in CON_VALOR
            continue
        pos.append(a)
    if sub in ("estado", "puertas"):
        return pos[0] if pos else None
    if sub in ("contacto", "encargos", "encargo", "lanzar", "reintentar", "config", "pausar", "reanudar", "leccion", "parte", "propuesta", "vigilancia", "preguntar", "ordenar"):
        return pos[0] if pos else None
    if sub in ("datos", "tanda", "wiki", "gestion", "aterrizaje", "ia"):
        return pos[1] if len(pos) > 1 else None
    if sub == "plan":
        return pos[1] if len(pos) > 1 else None
    return None


def orden_hseo(args: list) -> str | None:
    if not args:
        return "hseo sin orden"
    sub = args[0]
    if sub in ("-h", "--help"):
        return None
    if sub not in HSEO_SOLA | HSEO_APROBAR:
        return f"hseo {sub} no es una orden conocida"
    cli = cliente_de(args)
    if not CARTERA:
        if sub in ("preguntar", "ordenar", "novedad", "mejora", "cuaderno"):
            return "eso lo hace la coordinadora (hablar con los encargados, novedades, mejoras del sistema)"
        if sub == "alta":
            return "dar de alta otra web lo hace la coordinadora"
        ver = sub == "modelos" and args[1:2] in (["ver"], [])
        lectura_global = sub in ("clientes", "puerta", "lecciones") or (sub == "pipelines" and cli is None) or (ver and cli is None)
        if not lectura_global and cli != AMBITO:
            return f"solo puede actuar sobre {AMBITO}"
    texto = " ".join(args)
    if sub in HSEO_SOLA:
        if sub == "mcp" and args[1:2] == ["conectar"]:   # pide un código a una persona: con su aprobación
            APROBAR.append(f"hseo {' '.join(args)[:200]}")
            return None
        if sub == "aterrizaje" and args[1:2] in (["omitir"], ["empezar"]):
            APROBAR.append(f"hseo {' '.join(args)[:200]}")
            return None
        if sub == "lanzar":
            pos = [a for a in args[1:] if not a.startswith("--")]
            if "--excepcion" in args:
                APROBAR.append(f"Lanzar «{pos[1] if len(pos) > 1 else '?'}» para {cli} saltándose sus políticas (congelación o tope)")
            elif len(pos) > 1 and con_coste(pos[1], cli or ""):
                APROBAR.append(f"Lanzar «{pos[1]}» para {cli}: tiene coste externo (APIs de pago)")
        return None
    if sub == "modelos" and args[1:2] in (["ver"], []):
        return None
    APROBAR.append(f"hseo {texto[:300]}")
    return None


def segmento(seg: list, cwd: str) -> str | None:
    while seg and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", seg[0]):
        seg = seg[1:]
    if not seg:
        return None
    h = es_hseo(seg, cwd)
    if h is not None:
        return orden_hseo(h)
    cmd, args = os.path.basename(seg[0]), seg[1:]
    for a in args:   # leer está bien, pero no los secretos ni el resto de Hermes
        if a.startswith("-"):
            continue
        r = ruta(a, cwd)
        if SECRETOS.search(r):
            return "los secretos y los aprobadores no se leen"
        if dentro(r, os.path.join(HOME, ".hermes")) and not (dentro(r, HSEO) or any(dentro(r, x) for x in ARNES_RUTAS)):
            return "el resto de Hermes no se lee desde aquí"
        if not CARTERA and dentro(r, CLIENTES) and not dentro(r, os.path.join(CLIENTES, AMBITO)):
            return f"solo lee las carpetas de {AMBITO}"
    if cmd in LECTURA:
        return None
    if cmd == "find":
        return None if not any(a in ("-exec", "-execdir", "-delete", "-ok", "-fprint", "-fls") for a in args) else "find con acciones"
    if cmd == "sed":
        return None if "-n" in args and not any(a.startswith("-i") or a.startswith("--in-place") for a in args) else "sed que no es solo lectura (-n)"
    if cmd == "curl":
        if any(a in ("-X", "--request", "-d", "--data", "--data-raw", "--data-binary", "-F", "--form", "-T", "--upload-file",
                     "-o", "--output", "-O", "-K", "--config", "-u", "--user", "-H", "--header") or a.startswith(("-d", "-X", "-o"))
               for a in args):
            return "curl solo para leer una página (sin enviar datos ni guardar ficheros)"
        return None
    if cmd == "git":
        d = cwd
        while args[:1] == ["-C"] and len(args) >= 2:
            d = ruta(args[1], d); args = args[2:]
        sub = args[0] if args else ""
        if any(dentro(d, w) for w in ESCRIBE if w.endswith("wiki")) or (CARTERA and dentro(d, os.path.join(HSEO, "wiki"))):
            return None if sub not in ("push", "remote") else "publicar el wiki lo decide una persona"
        return None if sub in GIT_LECTURA else f"git {sub} (solo lectura fuera de su wiki)"
    return f"la orden «{cmd}» no está permitida (lectura o hseo)"


def terminal(c: str, cwd: str) -> None:
    if re.search(r"\$\(|`|<\(|>\(", c):
        bloquear("sin sustituciones de órdenes ($( ), ``)")
    sin_null = re.sub(r"\d?>&\d|\d?>\s*/dev/null", "", c)
    if ">" in sin_null:
        bloquear("sin redirecciones a ficheros: para escribir en el wiki usa write_file")
    if re.search(r"hseo_(puertas|encargos|clientes|etapa|modelos|pipelines|cli)\.py|firmar|decidir|etapa\.sh|guardia\.py", c):
        bloquear("los módulos del arnés no se llaman directamente: usa hseo")
    try:
        lex = shlex.shlex(sin_null, posix=True, punctuation_chars=";&|")
        lex.whitespace_split = True
        toks = list(lex)
    except ValueError:
        bloquear("orden que no se puede analizar (comillas sin cerrar)")
    seg, d = [], cwd
    for t in toks + [";"]:
        if t and set(t) <= set(";&|"):
            if seg:
                if os.path.basename(seg[0]) == "cd" and len(seg) > 1:
                    d = ruta(seg[1], d)
                m = segmento(seg, d)
                if m:
                    bloquear(m)
            seg = []
        else:
            seg.append(t)


def main() -> None:
    try:
        ev = json.load(sys.stdin)
    except ValueError:
        bloquear("evento ilegible")
    herramienta = ev.get("tool_name") or ""
    entrada = ev.get("tool_input") or {}
    base = os.path.join(CLIENTES, AMBITO) if not CARTERA else HSEO
    if herramienta in ("execute_code", "delegate_task", "cronjob"):
        bloquear(f"sin {herramienta}")
    if not CARTERA and herramienta not in HERRAMIENTAS_ENCARGADO:
        bloquear(f"la herramienta {herramienta} no está entre las del encargado")
    if herramienta == "search_files":
        p = ruta(str(entrada.get("path") or entrada.get("directory") or base), base)
        if SECRETOS.search(p) or (not CARTERA and not dentro(p, os.path.join(CLIENTES, AMBITO)) and not any(dentro(p, x) for x in ARNES_RUTAS)):
            bloquear(f"solo busca en las carpetas de {AMBITO}" if not CARTERA else "los secretos no se buscan")
        sys.exit(0)
    if herramienta in ("write_file", "patch"):
        p = ruta(str(entrada.get("path") or entrada.get("file_path") or ""), base)
        if "/.git/" in p + "/" or not any(dentro(p, w) for w in ESCRIBE):
            bloquear(f"solo escribe en su wiki y en briefs/, no en {p}")
        sys.exit(0)
    if herramienta == "read_file":
        p = ruta(str(entrada.get("path") or entrada.get("file_path") or ""), base)
        if SECRETOS.search(p):
            bloquear("los secretos no se leen")
        if not CARTERA and dentro(p, CLIENTES) and not dentro(p, os.path.join(CLIENTES, AMBITO)):
            bloquear(f"solo lee las carpetas de {AMBITO}")
        sys.exit(0)
    if herramienta == "terminal":
        terminal(str(entrada.get("command") or ""), ruta(str(entrada.get("workdir") or entrada.get("cwd") or base), base))
        if APROBAR and not CARTERA:   # el encargado nunca pide aprobaciones: un «sí» de un tercero no debe valer
            bloquear("eso necesita la aprobación de la persona: explícale qué harías y que se lo pida a la coordinadora ("
                     + "; ".join(APROBAR)[:200] + ")")
        if APROBAR:   # Hermes la pasa a su aprobación humana; sin respuesta (o en un cron) se deniega
            print(json.dumps({"action": "approve", "message": "; ".join(APROBAR),
                              "rule_key": "hermes-seo:" + re.sub(r"\W+", "-", APROBAR[0][:40])}, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()
