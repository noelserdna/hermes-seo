"""Puertas de hermes-seo: el núcleo común a todos los canales (Telegram, correo, local) y el notario.
Copiado y adaptado de hermes-sdd (hsdd_nucleo.py, firmar.sh).

  «El ejecutor nunca firma; el notario nunca decide; el orquestador nunca interpreta.»

Una puerta se abre al acabar la última etapa de una pipeline que la declara (o la abre el vigía de mantenimiento).
Vive SOLO en HERMES_SEO_HOME/puertas/<id>.json, fuera del alcance de las etapas. Un canal enseña la puerta y traduce
el gesto de una persona en decidir(); queda una ventana para deshacer; después el notario (firmar) comprueba quién
decidió y ejecuta lo aprobado: publicar con el adaptador del cliente, lanzar otra pipeline, rehacer desde una etapa
con lo que se pidió, o cerrar el encargo.

Siempre decide una persona. Con un aviso grave de la revisión (p. ej. la verificación pidió cambios) no se puede
aprobar: solo pedir cambios o descartar; la salida de emergencia es «decidir-local --forzar <motivo>», que queda escrita.

CLI:
  hseo_puertas.py listar [--todas]
  hseo_puertas.py ver <puerta>
  hseo_puertas.py abrir <cliente> <encargo>
  hseo_puertas.py decidir-local <puerta> <verbo> [texto] [--forzar MOTIVO]   (canal local: decide y firma al momento)
  hseo_puertas.py deshacer <puerta> <persona>
  hseo_puertas.py firmar <puerta>  ·  vencidas               (lo hace el gateway al acabar la ventana)
"""
from __future__ import annotations

import argparse
import getpass
import importlib.util
import json
import os
import re
import secrets
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
PL = _cargar("hseo_pipelines")
E = _cargar("hseo_encargos")
Rechazo = B.Rechazo

APRUEBA = ("acepto", "algunas")   # los verbos que ejecutan lo aprobado (con un aviso grave, bloqueados)
DESHACER_DEFECTO_S = 180
EMOJI = {"alta": "🧭", "plan-tecnico": "🛠", "plan-editorial": "🗺", "publicar": "🚀", "cambio-tecnico": "🔧",
         "decision": "📊", "veredicto": "⚖️", "mantenimiento": "🩺", "difusion": "📣"}
_APROBAR = {"verbo": "acepto", "etiqueta": "✅ De acuerdo"}
_CAMBIOS = {"verbo": "cambios", "etiqueta": "✏️ Cambios", "texto": True}
_NO = {"verbo": "rechazo", "etiqueta": "❌ No", "texto": True}
OPCIONES = {
    "alta": [{"verbo": "acepto", "etiqueta": "✅ Ya está lo que faltaba"}, {**_CAMBIOS, "etiqueta": "✏️ Falta algo"},
             {"verbo": "descarto", "etiqueta": "🗑 Dejarlo", "texto": True}],
    "plan-tecnico": [_APROBAR, _CAMBIOS, _NO],
    "plan-editorial": [_APROBAR, _CAMBIOS, _NO],
    "decision": [_APROBAR, _CAMBIOS, _NO],
    "veredicto": [_APROBAR, _CAMBIOS, _NO],
    "publicar": [{"verbo": "acepto", "etiqueta": "🚀 Publicar"}, {**_CAMBIOS, "etiqueta": "✏️ Cambiar algo"},
                 {"verbo": "descarto", "etiqueta": "🗑 Descartar", "texto": True}],
    "cambio-tecnico": [{"verbo": "acepto", "etiqueta": "🔧 Aplicar"}, _CAMBIOS,
                       {"verbo": "descarto", "etiqueta": "🗑 Descartar", "texto": True}],
    "difusion": [{"verbo": "acepto", "etiqueta": "📣 Todas"}, {"verbo": "algunas", "etiqueta": "☑️ Solo algunas", "texto": True},
                 _NO],
    "mantenimiento": [{"verbo": "cambio", "etiqueta": "🛠 Lanzar arreglo"},
                      {"verbo": "ignoro", "etiqueta": "🔕 Ignorar", "texto": True}],
}


def graves(puerta: dict) -> int:
    """Avisos graves de la revisión mecánica (hseo_revision) guardados en la puerta."""
    try:
        return int((puerta.get("revision") or {}).get("graves") or 0)
    except (TypeError, ValueError):
        return 0


def opciones_vigentes(puerta: dict) -> list:
    """Las opciones que se ofrecen: sin la de aprobar si hay un aviso grave."""
    ops = puerta.get("opciones") or []
    return [o for o in ops if o.get("verbo") not in APRUEBA] if graves(puerta) else ops


# ── utilidades ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _dir() -> Path:
    return B.home() / "puertas"


def indice(gid: str) -> Path:
    if not re.fullmatch(r"g[0-9a-f]{8,40}", gid or ""):
        raise Rechazo("id de puerta no válido")
    return _dir() / f"{gid}.json"


def leer(gid: str) -> dict:
    p = B.leer(indice(gid))
    if not p:
        raise Rechazo("No conozco esta puerta")
    return p


def puertas(estados=("abierta", "decidida")) -> list:
    d = _dir()
    out = [B.leer(f) for f in sorted(d.glob("g*.json"))] if d.is_dir() else []
    return [p for p in out if p and p.get("estado") in estados]


def _segundos(clave: str, defecto: int) -> int:
    if os.environ.get("HERMES_SEO_DESHACER_S"):
        return int(os.environ["HERMES_SEO_DESHACER_S"])
    try:
        v = int((B.leer(B.home() / "seo.json", {}) or {}).get(clave) or defecto)
    except (TypeError, ValueError):
        v = defecto
    return min(max(v, 0), 86400)


def deshacer_s() -> int:
    return _segundos("deshacer_s", DESHACER_DEFECTO_S)




def persona_de(canal: str, ident) -> tuple:
    """Persona de aprobadores.json cuya identidad en `canal` es `ident` → (clave, datos) o (None, None)."""
    for clave, p in (B.leer(B.home() / "aprobadores.json", {}) or {}).items():
        if str(ident) and str((p.get("canales") or {}).get(canal, "")) == str(ident):
            return clave, p
    return None, None


def puede_decidir(persona: str, slug: str) -> bool:
    p = (B.leer(B.home() / "aprobadores.json", {}) or {}).get(persona) or {}
    clientes = p.get("clientes", ["*"])
    return bool(p) and ("*" in clientes or slug in clientes)


# ── abrir ───────────────────────────────────────────────────────────────────────────────────────────────────────────
def _resumen_de(d: Path, nombre: str, maximo: int = 1800) -> str:
    f = d / nombre
    if not f.exists():
        return ""
    t = f.read_text(errors="replace").strip()
    if f.suffix == ".json":
        try:
            t = json.dumps(json.loads(t), ensure_ascii=False, indent=1)
        except ValueError:
            pass
    return t if len(t) <= maximo else t[:maximo].rsplit("\n", 1)[0] + "\n…"


def _resumen_publicacion(d: Path) -> str:
    """publicacion.json contado para una persona (lo que se va a publicar), en vez del JSON en bruto."""
    pub = B.leer(d / "publicacion.json")
    if not isinstance(pub, dict):
        return _resumen_de(d, "publicacion.json")
    l = []
    if pub.get("titulo"):
        l.append(f"📰 {pub['titulo']}")
    if pub.get("url"):
        l.append(f"🔗 {pub['url']}")
    if pub.get("meta_descripcion"):
        l.append(f"📝 {pub['meta_descripcion']}")
    for c in (pub.get("cambios") or [])[:8]:
        l.append(f"• {c.get('accion', 'cambio')}: «{str(c.get('antes', '—'))[:160]}» → «{str(c.get('despues', '—'))[:160]}»")
    if pub.get("pr"):
        l.append(f"🔀 PR: {pub['pr']}")
    if pub.get("hipotesis"):
        l.append(f"🎯 Hipótesis: {pub['hipotesis']}")
    revs = [f"{k}: {pub[k]}" for k in ("verificacion", "lectura") if pub.get(k)]
    if revs:
        l.append("🔎 " + " · ".join(revs))
    if pub.get("como_deshacer"):
        l.append(f"↩ Cómo deshacerlo: {pub['como_deshacer']}")
    if pub.get("error"):
        l.append(f"⚠️ {pub['error']}")
    return "\n".join(l)


def _revision(slug: str, eid: str | None, tipo: str) -> dict:
    """Revisión mecánica del encargado (hseo_revision.py, sin IA). Si aún no existe o falla, sin avisos."""
    try:
        return _cargar("hseo_revision").revisar(slug, eid, tipo)
    except Exception:
        return {"avisos": [], "graves": 0}


def abrir(slug: str, eid: str | None = None, tipo: str | None = None, titulo: str = "", texto: str = "",
          hallazgos: list | None = None) -> dict:
    """Abre la puerta de un encargo (la de su pipeline) o una suelta (mantenimiento: tipo + texto + hallazgos)."""
    cfg = C.leer(slug)
    enc, p = None, None
    if eid:
        enc = E.leer(slug, eid)
        p = PL.cargar(enc["pipeline"], slug)
        tipo = (enc.get("puerta") or {}).get("tipo")
        if not tipo:
            raise Rechazo(f"La pipeline {enc['pipeline']} no tiene puerta")
        if any(x.get("encargo") == eid for x in puertas()):
            raise Rechazo(f"El encargo {eid} ya tiene una puerta pendiente")
        d = E.carpeta(slug, eid)
        salidas = [s.get("salida") for s in p["etapas"] if s["id"] in [x["id"] for x in enc["etapas"]] and s.get("salida")]
        principal = salidas[-1] if salidas else ""
        resumen = _resumen_publicacion(d) if principal == "publicacion.json" else _resumen_de(d, principal)
        detalles = [f"{tipo_param}: {v}" for tipo_param, v in (enc.get("params") or {}).items()]
        titulo = titulo or f"{EMOJI.get(tipo, '🚪')} {p['nombre']} · {cfg['nombre']}"
        texto = texto or ("\n".join(detalles) + ("\n\n" if detalles else "") + resumen +
                          f"\n\n📁 {d}" + (f"\n📄 {', '.join(s for s in salidas if (d / s).exists())}" if salidas else ""))
    if tipo not in OPCIONES:
        raise Rechazo(f"Tipo de puerta desconocido: {tipo}")
    rev = _revision(slug, eid, tipo)
    if rev.get("avisos"):
        lineas = [f"{'⛔' if a.get('grave') else '⚠️'} {a['texto']}" for a in rev["avisos"]]
        texto = f"🧭 Encargado: {len(rev['avisos'])} aviso(s)\n" + "\n".join(lineas) + "\n\n" + texto
    gid = f"g{int(time.time()):x}{secrets.token_hex(3)}"
    puerta = {"id": gid, "tipo": tipo, "cliente": slug, "encargo": eid, "pipeline": enc and enc["pipeline"],
              "titulo": titulo, "texto": texto, "opciones": OPCIONES[tipo],
              "al_aprobar": ((enc or {}).get("puerta") or {}).get("al_aprobar", "nada"),
              "rehacer": ((enc or {}).get("puerta") or {}).get("rehacer") or (enc["etapas"][-1]["id"] if enc else None),
              "hallazgos": hallazgos or [], "revision": rev, "creada": B.ahora(), "estado": "abierta"}
    with B.cerrojo("puertas"):
        B.escribir(indice(gid), puerta)
    if enc:
        enc["puerta_id"] = gid
        enc["estado"] = "en-puerta"
        E.guardar(slug, enc)
        try:
            _cargar("hseo_publicacion").aligerar(slug, eid)
        except Exception:
            pass
    return puerta


# ── decidir y deshacer ─────────────────────────────────────────────────────────────────────────────────────────────
def _registrar(puerta: dict, verbo: str, texto: str, actor: dict, prueba: dict, ventana_s: int) -> dict:
    puerta.update(estado="decidida", firmar_en=time.time() + ventana_s,
                  decision={"verbo": verbo, "texto": texto, "actor": actor, "prueba": prueba, "at": B.ahora()})
    B.escribir(indice(puerta["id"]), puerta)
    return puerta


def decidir(gid: str, verbo: str, texto: str, persona: str, canal: str, ident, prueba: dict | None = None) -> dict:
    """Registra la decisión de `persona` (identificada por el canal) y abre la ventana para deshacer. Con un aviso
    grave de la revisión no se aprueba (salvo `forzar`, solo desde el canal local, con su motivo por escrito)."""
    forzar = (prueba or {}).get("forzado", "")
    with B.cerrojo("puertas"):
        puerta = leer(gid)
        if puerta.get("estado") != "abierta":
            raise Rechazo("Esta puerta ya está resuelta")
        if persona_de(canal, ident)[0] != persona or not puede_decidir(persona, puerta["cliente"]):
            raise Rechazo("No estás autorizado para decidir esta puerta")
        opcion = next((o for o in puerta["opciones"] if o["verbo"] == verbo), None)
        if not opcion:
            raise Rechazo("Opción no válida")
        if verbo in APRUEBA and graves(puerta) and not (forzar and canal == "local"):
            raise Rechazo("Tiene un aviso grave de la revisión (🧭 ⛔): solo se puede pedir cambios o descartar")
        texto = (texto or "").strip()
        if opcion.get("texto") and not texto:
            raise Rechazo(f"«{opcion['etiqueta']}» necesita un motivo")
        return _registrar(puerta, verbo, texto, {"persona": persona, "canal": canal, "id": str(ident)},
                          prueba or {}, deshacer_s())


def deshacer(gid: str, persona: str) -> dict:
    """Quien decidió; solo antes de la firma."""
    with B.cerrojo("puertas"):
        puerta = leer(gid)
        dec = puerta.get("decision") or {}
        if puerta.get("estado") != "decidida" or not persona or (dec.get("actor") or {}).get("persona") != persona:
            raise Rechazo("Ya no se puede deshacer")
        puerta["estado"] = "abierta"
        puerta.pop("decision", None)
        puerta.pop("firmar_en", None)
        B.escribir(indice(gid), puerta)
        return puerta


def marcar(gid: str, **campos) -> dict:
    """Campos de presentación de un canal (mensaje de Telegram…)."""
    with B.cerrojo("puertas"):
        puerta = leer(gid)
        for k, v in campos.items():
            if k in ("estado", "decision", "firmar_en", "opciones", "cliente", "encargo", "revision"):
                raise Rechazo(f"«{k}» no lo marca un canal")
            if v is None:
                puerta.pop(k, None)
            else:
                puerta[k] = v
        B.escribir(indice(gid), puerta)
        return puerta


# ── notario ─────────────────────────────────────────────────────────────────────────────────────────────────────────
def _valida_actor(puerta: dict) -> str:
    """Comprueba de nuevo quién decidió. Devuelve el texto de firma («Ana (telegram)»)."""
    dec = puerta.get("decision") or {}
    actor = dec.get("actor") or {}
    clave, datos = persona_de(actor.get("canal", ""), actor.get("id", ""))
    if not clave or clave != actor.get("persona") or not puede_decidir(clave, puerta["cliente"]):
        raise Rechazo("Quien decidió no está autorizado en ese canal")
    return f"{(datos or {}).get('nombre') or clave} ({actor.get('canal')})"


def _aplicar(puerta: dict, firma: str) -> str:
    """Ejecuta lo decidido. Devuelve una línea con el resultado."""
    dec = puerta["decision"]
    verbo, texto = dec["verbo"], dec.get("texto", "")
    slug, eid = puerta["cliente"], puerta.get("encargo")
    enc = E.leer(slug, eid) if eid else None
    if verbo in ("acepto", "cambio", "algunas"):
        accion = puerta.get("al_aprobar") or "nada"
        if puerta["tipo"] == "mantenimiento" and verbo == "cambio":
            accion = "pipeline:cambio-seo"
        if accion == "publicar":
            try:
                res = _cargar("hseo_publicacion").publicar(slug, eid, firma)
            except Rechazo:
                raise
            except Exception as e:
                raise Rechazo(f"No se pudo publicar: {e}")
            resultado = f"publicado: {res}"
        elif accion == "gestiones":
            sel = None
            if verbo == "algunas":
                sel = [int(x) for x in re.findall(r"\d+", texto)]
                if not sel:
                    raise Rechazo("«Solo algunas» necesita los números, p. ej. «1,3»")
            resultado = _cargar("hseo_autoridad").aplicar(slug, eid, sel, firma)
        elif accion.startswith("pipeline:"):
            params = {"que": "\n".join(h if isinstance(h, str) else json.dumps(h, ensure_ascii=False)
                                       for h in puerta.get("hallazgos") or [])[:2000]} if puerta["tipo"] == "mantenimiento" else {}
            nuevo = E.lanzar(slug, accion.split(":", 1)[1], params, quien=f"notario: puerta {puerta['id']} ({firma})",
                             origen=eid)
            resultado = f"lanzado {nuevo['id']}"
        elif accion.startswith("script:"):
            resultado = _script(slug, eid, accion[len("script:"):], firma)
        else:
            resultado = "aprobado"
        if enc:
            enc["estado"] = "cerrado"
    elif verbo == "cambios":
        if not enc:
            raise Rechazo("Esta puerta no tiene un encargo que rehacer")
        E.rehacer_desde(slug, eid, puerta.get("rehacer") or enc["etapas"][-1]["id"], texto, firma)
        enc = E.leer(slug, eid)
        resultado = f"se rehace desde {puerta.get('rehacer')}"
    elif verbo in ("rechazo", "descarto", "ignoro"):
        if enc:
            enc["estado"] = "descartado"
        resultado = "descartado" if verbo != "ignoro" else "ignorado"
    else:
        raise Rechazo(f"Verbo desconocido: {verbo}")
    if enc:
        E.guardar(slug, enc)
        if enc.get("estado") == "descartado":   # al publicar ya lo quita el despliegue; al descartar, aquí
            _cargar("hseo_publicacion").limpiar_worktree(slug, eid)
    return resultado


def _script(slug: str, eid: str | None, orden: str, firma: str) -> str:
    """al_aprobar «script:<fichero> [args]»: un script de extensiones/ de la web, desacoplado, con su log."""
    import subprocess
    partes = orden.replace("{encargo}", eid or "").replace("{carpeta}", str(E.carpeta(slug, eid)) if eid else "").split()
    ext = (C.carpeta(slug) / "extensiones").resolve()
    ruta = (ext / partes[0]).resolve()
    if not str(ruta).startswith(str(ext) + os.sep) or not ruta.is_file():
        raise Rechazo(f"No encuentro el script {partes[0]} en las extensiones de la web")
    log = C.carpeta(slug) / "logs" / f"script-{eid or 'puerta'}-{partes[0]}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "HSEO_FIRMA": firma, "HSEO_ENCARGO": eid or "", "HERMES_SEO_HOME": str(B.home())}
    subprocess.Popen(B.desacoplar(["bash", str(ruta), *partes[1:]]), start_new_session=True, cwd=str(C.carpeta(slug)), env=env,
                     stdout=open(log, "w"), stderr=subprocess.STDOUT)
    return f"lanzado {partes[0]} (registro en logs/{log.name})"


def firmar(gid: str, ahora: float | None = None) -> dict:
    """El notario: valida, ejecuta lo decidido y lo registra. Idempotente: una puerta firmada no se vuelve a firmar."""
    with B.cerrojo("notario"):
        puerta = leer(gid)
        if puerta.get("estado") == "firmada":
            return puerta
        if puerta.get("estado") != "decidida":
            raise Rechazo("Esta puerta no está decidida")
        if (ahora or time.time()) < float(puerta.get("firmar_en") or 0):
            raise Rechazo("Aún está abierta la ventana para deshacer")
        try:
            firma = _valida_actor(puerta)
            resultado = _aplicar(puerta, firma)
        except Rechazo as e:
            with B.cerrojo("puertas"):
                p = leer(gid)
                p.update(estado="error", error=str(e), error_at=B.ahora())
                B.escribir(indice(gid), p)
            raise
        with B.cerrojo("puertas"):
            p = leer(gid)
            p.update(estado="firmada", firmada=B.ahora(), firma=firma, resultado=resultado)
            B.escribir(indice(gid), p)
        dec = p["decision"]
        B.anotar(C.carpeta(p["cliente"]) / "puertas.jsonl", {
            "ts": p["firmada"], "puerta": gid, "tipo": p["tipo"], "encargo": p.get("encargo"), "verbo": dec["verbo"],
            "texto": dec.get("texto", ""), "persona": dec["actor"].get("persona"), "canal": dec["actor"].get("canal"),
            "firma": firma, "resultado": resultado, "forzado": (dec.get("prueba") or {}).get("forzado", ""),
            "segundos_hasta_decidir": _segundos_entre(p.get("creada"), dec.get("at"))})
        try:   # la memoria de la web: decisiones y correcciones (sin modelo; nunca frena al notario)
            _cargar("hseo_wiki").regenerar_decisiones(p["cliente"])
        except Exception:   # noqa: BLE001
            pass
        return p


def _segundos_entre(a, b) -> int:
    from datetime import datetime
    try:
        f = "%Y-%m-%dT%H:%M:%SZ"
        return int((datetime.strptime(b, f) - datetime.strptime(a, f)).total_seconds())
    except Exception:
        return 0


def vencidas() -> list:
    """Firma las puertas decididas cuya ventana para deshacer ya pasó. Devuelve [(id, ok, mensaje)]."""
    out = []
    for p in puertas(("decidida",)):
        if time.time() >= float(p.get("firmar_en") or 0):
            try:
                r = firmar(p["id"])
                out.append((p["id"], True, r.get("resultado", "")))
            except Rechazo as e:
                out.append((p["id"], False, str(e)))
    return out


def decidir_local(gid: str, verbo: str, texto: str = "", forzar: str = "") -> dict:
    """Canal local (plan B sin Telegram): la persona en esta máquina decide y se firma al momento. `forzar` (un motivo)
    permite aprobar una puerta con aviso grave; queda en puertas.jsonl."""
    usuario = getpass.getuser()
    clave, _ = persona_de("local", usuario)
    if not clave:
        raise Rechazo(f"El usuario {usuario} no está en aprobadores.json (canales.local)")
    if forzar is not None and forzar != "" and not forzar.strip():
        raise Rechazo("--forzar necesita un motivo")
    decidir(gid, verbo, texto, clave, "local", usuario, {"forzado": forzar.strip()} if forzar else None)
    with B.cerrojo("puertas"):
        p = leer(gid)
        p["firmar_en"] = 0
        B.escribir(indice(gid), p)
    return firmar(gid)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="hseo_puertas.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    l = sub.add_parser("listar"); l.add_argument("--todas", action="store_true")
    sub.add_parser("ver").add_argument("puerta")
    a = sub.add_parser("abrir"); a.add_argument("cliente"); a.add_argument("encargo")
    dl = sub.add_parser("decidir-local"); dl.add_argument("puerta"); dl.add_argument("verbo"); dl.add_argument("texto", nargs="?", default="")
    dl.add_argument("--forzar", default="")
    dh = sub.add_parser("deshacer"); dh.add_argument("puerta"); dh.add_argument("persona")
    sub.add_parser("firmar").add_argument("puerta")
    sub.add_parser("vencidas")
    x = ap.parse_args(argv)
    try:
        if x.cmd == "listar":
            for p in puertas(("abierta", "decidida", "error", "firmada") if x.todas else ("abierta", "decidida", "error")):
                print(f"{p['id']}  {p['estado']:9} {p['cliente']:16} {p['titulo']}")
        elif x.cmd == "ver":
            print(json.dumps(leer(x.puerta), ensure_ascii=False, indent=2))
        elif x.cmd == "abrir":
            print(abrir(x.cliente, x.encargo)["id"])
        elif x.cmd == "decidir-local":
            p = decidir_local(x.puerta, x.verbo, x.texto, x.forzar)
            print(f"Firmada por {p['firma']}: {p['resultado']}")
        elif x.cmd == "deshacer":
            deshacer(x.puerta, x.persona); print("deshecha")
        elif x.cmd == "firmar":
            p = firmar(x.puerta); print(f"Firmada por {p['firma']}: {p['resultado']}")
        elif x.cmd == "vencidas":
            for gid, ok, msg in vencidas():
                print(f"{gid} {'ok' if ok else 'ERROR'} {msg}")
    except Rechazo as e:
        print(str(e), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
