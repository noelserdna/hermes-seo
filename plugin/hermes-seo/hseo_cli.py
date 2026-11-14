"""hseo: las acciones de la coordinadora y de los encargados sobre hermes-seo. Es su ÚNICA vía para mover el sistema
(el guardia, encargado/guardia.py, bloquea todo lo demás y decide qué acciones necesitan la aprobación de la persona).

No hay ninguna orden para decidir o firmar puertas, ni para publicar: eso solo pasa en una puerta (una persona, o Jev
si se lo delegaron), y lo ejecuta el notario.

  Consultar (sola)
    hseo clientes · hseo estado [cliente] · hseo encargos <cliente> [--todos] · hseo encargo <cliente> <id>
    hseo puertas [cliente] · hseo puerta <id> · hseo pipelines [--cliente C] · hseo plan <pipeline> <cliente>
    hseo modelos ver [--cliente C] · hseo jev ver
    hseo datos resumen <cliente> [--dias 28] · hseo datos comparar <cliente> <cambio> · hseo datos recoger <cliente>
  Trabajar (sola, y lo cuenta)
    hseo leccion <cliente> <etapa> "<regla general>" <encargo|puerta>…   (la confirma una persona) · hseo lecciones
    hseo lanzar <cliente> <pipeline> [--param k=v]… [--brief TEXTO]
    hseo reintentar <cliente> <encargo> <etapa>          (una vez por etapa; después, una persona)
  Cambiar el sistema (con la aprobación de la persona)
    hseo alta <slug> <dominio> [--estado nueva|repo|wordpress|sin-acceso] [--nombre N]
    hseo config <cliente> <clave.con.puntos> <valor>
    hseo pausar <cliente|todo> · hseo reanudar <cliente|todo>
    hseo jev modo <humano|consejo|piloto|auto> [cliente] · hseo jev umbral|umbral-auto <p> · hseo jev piloto <tipos>
    hseo modelos perfil <calidad|equilibrado|rapido> · hseo modelos poner <etapa> <modelo|-> [--cliente C]
    hseo lanzar … --excepcion                            (salta la congelación o el tope: lo pidió una persona)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
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
PL = _cargar("hseo_pipelines")
E = _cargar("hseo_encargos")
PU = _cargar("hseo_puertas")
M = _cargar("hseo_modelos")
Rechazo = B.Rechazo


def quien() -> str:
    """Quién pide la acción: la persona (si el canal la pasa) o el perfil de Hermes que la ejecuta."""
    return os.environ.get("HSEO_QUIEN") or os.environ.get("HERMES_PROFILE") or os.environ.get("USER", "")


def estado(slug: str | None = None) -> str:
    slugs = [slug] if slug else C.listar()
    if not slugs:
        return "Aún no hay ninguna web dada de alta."
    lineas = []
    global_pausa = (B.home() / "pausa").exists()
    if global_pausa:
        lineas.append("⏸ Todo en pausa")
    for s in slugs:
        cfg = C.leer(s)
        lineas.append(f"🌐 {C.resumen(cfg)}")
        abiertos = E.listar(s, abiertos=True)
        for e in abiertos:
            hechas = _etapas_hechas(s, e["id"])
            lineas.append(f"  • {e['nombre']} ({e['id']}): {e.get('estado')} · {hechas}/{len(e['etapas'])} etapas")
        for p in PU.puertas(("abierta", "decidida", "error")):
            if p["cliente"] == s:
                lineas.append(f"  🚪 {p['titulo']} [{p['estado']}] ({p['id']})" + (f" — {p['error']}" if p.get("error") else ""))
        if not abiertos:
            lineas.append("  (nada en marcha)")
    return "\n".join(lineas)


def _etapas_hechas(slug: str, eid: str) -> int:
    enc = E.leer(slug, eid)
    hechas = set()
    try:
        for l in (C.carpeta(slug) / "etapas.jsonl").read_text().splitlines():
            r = json.loads(l)
            if r.get("encargo") == eid and r.get("resultado") == "done":
                hechas.add(r["etapa"])
            elif r.get("encargo") == eid:
                hechas.discard(r["etapa"])
    except OSError:
        pass
    return len([s for s in enc["etapas"] if s["id"] in hechas])


def reintentar(slug: str, eid: str, etapa: str) -> dict:
    """Vuelve a lanzar una etapa parada (y las siguientes). Una vez por etapa y encargo; después lo decide una persona."""
    d = E.carpeta(slug, eid)
    previos = 0
    try:
        for l in (d / ".estado" / "historial.jsonl").read_text().splitlines():
            r = json.loads(l)
            previos += r.get("accion") == "reintentar" and r.get("desde") == etapa
    except OSError:
        pass
    if previos:
        raise Rechazo(f"La etapa {etapa} ya se reintentó una vez: que lo decida una persona (o pide cambios en la puerta)")
    enc = E.leer(slug, eid)
    if enc.get("estado") not in ("parado", "en-curso"):
        raise Rechazo(f"El encargo está «{enc.get('estado')}»: no hay nada que reintentar")
    enc = E.rehacer_desde(slug, eid, etapa, "", quien(), accion="reintentar")
    return enc


def pausar(objetivo: str, si: bool) -> str:
    if objetivo == "todo":
        f = B.home() / "pausa"
        if si:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_text(B.ahora() + "\n")
        else:
            f.unlink(missing_ok=True)
        return "Todo en pausa" if si else "Todo reanudado"
    C.config(objetivo, "politicas.pausado", si, quien())
    return f"{objetivo}: {'en pausa' if si else 'reanudado'}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hseo", description="Acciones de hermes-seo")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("clientes")
    sub.add_parser("estado").add_argument("cliente", nargs="?")
    x = sub.add_parser("encargos"); x.add_argument("cliente"); x.add_argument("--todos", action="store_true")
    x = sub.add_parser("encargo"); x.add_argument("cliente"); x.add_argument("id")
    sub.add_parser("puertas").add_argument("cliente", nargs="?")
    sub.add_parser("puerta").add_argument("id")
    sub.add_parser("pipelines").add_argument("--cliente")
    x = sub.add_parser("plan"); x.add_argument("pipeline"); x.add_argument("cliente")
    x = sub.add_parser("lanzar"); x.add_argument("cliente"); x.add_argument("pipeline")
    x.add_argument("--param", action="append", default=[]); x.add_argument("--brief", default="")
    x.add_argument("--excepcion", action="store_true")
    x = sub.add_parser("reintentar"); x.add_argument("cliente"); x.add_argument("encargo"); x.add_argument("etapa")
    x = sub.add_parser("datos"); x.add_argument("accion", choices=("recoger", "resumen", "comparar"))
    x.add_argument("cliente"); x.add_argument("cambio", nargs="?"); x.add_argument("--dias", type=int, default=28)
    x = sub.add_parser("leccion"); x.add_argument("cliente"); x.add_argument("etapa"); x.add_argument("regla")
    x.add_argument("evidencia", nargs="+")
    sub.add_parser("lecciones").add_argument("--todas", action="store_true")
    x = sub.add_parser("alta"); x.add_argument("slug"); x.add_argument("dominio")
    x.add_argument("--estado", default="nueva", choices=C.ESTADOS_WEB); x.add_argument("--nombre", default="")
    x = sub.add_parser("config"); x.add_argument("cliente"); x.add_argument("clave"); x.add_argument("valor")
    sub.add_parser("pausar").add_argument("objetivo")
    sub.add_parser("reanudar").add_argument("objetivo")
    x = sub.add_parser("jev"); x.add_argument("args", nargs="*")
    x = sub.add_parser("modelos"); x.add_argument("args", nargs="*"); x.add_argument("--cliente")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "clientes":
            print("\n".join(C.resumen(C.leer(s)) for s in C.listar()) or "Aún no hay ninguna web dada de alta.")
        elif a.cmd == "estado":
            print(estado(a.cliente))
        elif a.cmd == "encargos":
            for e in E.listar(a.cliente, abiertos=not a.todos):
                print(f"{e['id']:44} {e.get('estado', ''):11} {e.get('nombre', '')} · {e.get('creado', '')[:10]}")
        elif a.cmd == "encargo":
            print(json.dumps(E.leer(a.cliente, a.id), ensure_ascii=False, indent=2))
        elif a.cmd == "puertas":
            for p in PU.puertas(("abierta", "decidida", "error")):
                if not a.cliente or p["cliente"] == a.cliente:
                    print(f"{p['id']}  {p['estado']:9} {p['titulo']}")
        elif a.cmd == "puerta":
            p = PU.leer(a.id)
            print(f"{p['titulo']}\n\n{p['texto']}\n\n{PU.describir_jev(p)}".strip())
        elif a.cmd == "pipelines":
            for pid, p in PL.listar(a.cliente).items():
                print(f"{pid:22} {p.get('nombre', '')}: {p.get('descripcion', '')}")
        elif a.cmd == "plan":
            r = PL.plan(a.pipeline, a.cliente)
            mods = M.efectivos(a.cliente)
            for s in r["etapas"]:
                ej = (C.leer(a.cliente).get("ejecutores") or {}).get(s["id"]) or s.get("ejecutor", "hermes")
                quien_hace = "Claude Code" if ej == "claude" else s["perfil"]
                print(f"▶ {s['titulo']} ({quien_hace}, {mods.get(s['id'], (M.LIGERO, ''))[0]})")
            for s in r["saltadas"]:
                print(f"· {s['titulo']}: se salta, falta {', '.join(s['falta'])}")
        elif a.cmd == "lanzar":
            params = dict(kv.split("=", 1) for kv in a.param if "=" in kv)
            if len(params) != len(a.param):
                raise Rechazo("Cada --param va como clave=valor")
            e = E.lanzar(a.cliente, a.pipeline, params, a.brief, a.excepcion, quien())
            print(f"🚀 {e['nombre']} en marcha para {a.cliente} ({e['id']}): {len(e['etapas'])} etapas"
                  + (f"; se saltan {', '.join(s['id'] for s in e['saltadas'])}" if e["saltadas"] else ""))
        elif a.cmd == "reintentar":
            reintentar(a.cliente, a.encargo, a.etapa)
            print(f"🔁 {a.etapa} vuelve a la cola ({a.encargo})")
        elif a.cmd == "datos":
            D = _cargar("hseo_datos")
            if a.accion == "recoger":
                fallos = D.recoger(a.cliente)
                if fallos:
                    print(f"⚠️ No se pudieron recoger todos los datos de {a.cliente}:\n" + "\n".join(f"- {f}" for f in fallos))
            elif a.accion == "resumen":
                print(json.dumps(D.resumen(a.cliente, a.dias), ensure_ascii=False, indent=1))
            else:
                if not a.cambio:
                    raise Rechazo("uso: hseo datos comparar <cliente> <cambio>")
                print(json.dumps(D.comparar(a.cliente, a.cambio), ensure_ascii=False, indent=1))
        elif a.cmd == "leccion":
            l = _cargar("hseo_lecciones").proponer(a.cliente, a.etapa, a.regla, a.evidencia, quien())
            print(f"💡 Lección propuesta ({l['id']}): le llega a la persona para que la confirme.")
        elif a.cmd == "lecciones":
            for l in _cargar("hseo_lecciones").todas():
                if a.todas or l["estado"] in ("propuesta", "confirmada", "revisar"):
                    print(f"{l['id']}  {l['estado']:10} {l['etapa']:16} {l['regla']}")
        elif a.cmd == "alta":
            cfg = C.alta(a.slug, a.dominio, a.estado, a.nombre, quien())
            print(f"🌐 Alta hecha: {C.resumen(cfg)}\nSiguiente: completar su configuración y lanzar «alta».")
        elif a.cmd == "config":
            print(C.resumen(C.config(a.cliente, a.clave, a.valor, quien())))
        elif a.cmd in ("pausar", "reanudar"):
            print(pausar(a.objetivo, a.cmd == "pausar"))
        elif a.cmd == "jev":
            x = a.args or ["ver"]
            if x[0] == "ver":
                print(json.dumps(PU.config_jev(), ensure_ascii=False, indent=2))
            elif x[0] == "modo" and len(x) in (2, 3):
                PU.poner_modo(x[1], x[2] if len(x) == 3 else None)
                print(f"🤖 Jev en modo {x[1]}" + (f" para {x[2]}" if len(x) == 3 else " por defecto"))
            elif x[0] in ("umbral", "umbral-auto") and len(x) == 2:
                PU.ajustar_jev(**{x[0].replace("-", "_"): x[1]}); print("ok")
            elif x[0] == "piloto" and len(x) == 2:
                PU.ajustar_jev(piloto=x[1].split(",")); print("ok")
            else:
                raise Rechazo("uso: hseo jev ver | modo <modo> [cliente] | umbral <p> | umbral-auto <p> | piloto <tipos>")
        elif a.cmd == "modelos":
            x = a.args or ["ver"]
            if x[0] == "ver":
                nombres = dict(M.ETAPAS_MODELO)
                for e, (m, o) in M.efectivos(a.cliente).items():
                    print(f"{nombres.get(e, e):32} {m:12} ({o})")
            elif x[0] == "perfil" and len(x) == 2:
                M.poner_perfil(x[1]); print(M.NOMBRE_PERFIL[x[1]])
            elif x[0] == "poner" and len(x) == 3:
                M.poner(x[1], x[2], a.cliente, quien()); print("ok")
            else:
                raise Rechazo("uso: hseo modelos ver | perfil <p> | poner <etapa> <modelo|-> [--cliente C]")
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
