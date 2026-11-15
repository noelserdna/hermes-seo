"""hermes-seo — plugin de Hermes: puertas en Telegram, notario, comandos y el contexto de cada web en el prompt.

El canal no decide ni firma: (1) publica cada puerta abierta con sus botones en el tema de su web (o en el chat
principal), (2) convierte el toque de una persona autorizada en una decisión (hseo_puertas.decidir), (3) deja una
ventana para deshacer y (4) llama al notario (hseo_puertas.firmar), que valida y ejecuta. La identidad sale del update
de Telegram (from.id), nunca de un texto.

Los botones usan el prefijo «hs:» para convivir con otros plugins de puertas (hermes-sdd usa «g:»).
"""
from __future__ import annotations

import asyncio
import importlib.util
import logging
import os
import shutil
import sys
import time
from pathlib import Path

log = logging.getLogger("hermes_plugins.hermes_seo")
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
PU = _cargar("hseo_puertas")
_RT: dict = {"app": None}
PREFIJO = "hs"


def _path_cmds() -> str:
    dirs = [f"{Path.home()}/.local/bin", f"{Path.home()}/.npm-global/bin", "/opt/homebrew/bin", "/usr/local/bin", "/usr/bin", "/bin"]
    for cmd in ("hermes", "node", "claude", "jq"):
        p = shutil.which(cmd)
        if p and str(Path(p).parent) not in dirs:
            dirs.insert(0, str(Path(p).parent))
    return ":".join(dirs)


os.environ["PATH"] = _path_cmds() + ":" + os.environ.get("PATH", "")


def _arnes() -> Path:
    return Path((B.leer(B.home() / "instalacion.json", {}) or {}).get("root") or AQUI.parent.parent)


# ── dónde se publica ────────────────────────────────────────────────────────────────────────────────────────────────
def _destinos(puerta: dict) -> list:
    """[(chat_id, thread_id|None)]: el tema de la web si lo tiene; si no, el chat principal o los aprobadores."""
    try:   # la web, o «__cartera__» para lo que es de todas (lecciones): el tema 📊 Cartera si está configurado
        tg = ((B.leer(B.home() / "seo.json", {}) or {}).get("telegram_cartera") or {}) if puerta["cliente"] == "__cartera__" \
            else (C.leer(puerta["cliente"]).get("telegram") or {})
    except B.Rechazo:
        tg = {}
    if tg.get("chat_id"):
        return [(int(tg["chat_id"]), int(tg["thread_id"]) if tg.get("thread_id") else None)]
    home = os.environ.get("TELEGRAM_HOME_CHANNEL", "").strip()
    if home:
        return [(int(home), None)]
    return [(int(p["canales"]["telegram"]), None) for p in (B.leer(B.home() / "aprobadores.json", {}) or {}).values()
            if (p.get("canales") or {}).get("telegram")]


def _teclado(puerta: dict):
    from telegram import InlineKeyboardButton as Bt, InlineKeyboardMarkup as Mk
    if puerta.get("estado") == "decidida":
        return Mk([[Bt("↩ Deshacer", callback_data=f"{PREFIJO}:deshacer:{puerta['id']}")]])
    if puerta.get("estado") != "abierta":
        return None
    bs = [Bt(o["etiqueta"], callback_data=f"{PREFIJO}:{o['verbo']}:{puerta['id']}") for o in PU.opciones_vigentes(puerta)]
    return Mk([bs[i:i + 2] for i in range(0, len(bs), 2)])


def _render(puerta: dict) -> str:
    partes = [puerta["titulo"], "", puerta["texto"]]
    if PU.graves(puerta) and puerta.get("estado") == "abierta":
        partes += ["", "⛔ Tiene un aviso grave: solo se puede pedir cambios o descartar."]
    est = puerta.get("estado")
    dec = puerta.get("decision") or {}
    if est == "decidida":
        quien = (dec.get("actor") or {}).get("persona")
        falta = max(0, int(float(puerta.get("firmar_en") or 0) - time.time()))
        partes += ["", f"🕒 Decidido por {quien}: «{dec.get('verbo')}». Se ejecuta en {falta // 60} min {falta % 60} s si nadie lo deshace."]
    elif est == "firmada":
        partes += ["", f"✅ {puerta.get('firma')}: {puerta.get('resultado')}"]
    elif est == "error":
        partes += ["", f"⚠️ No se pudo completar: {puerta.get('error')}"]
    return "\n".join(partes)[:4000]


def _vista(puerta: dict) -> str:
    return "|".join([puerta.get("estado", ""), str((puerta.get("decision") or {}).get("at", ""))])


async def _publicar(bot, puerta: dict) -> None:
    enviados = []
    for chat, hilo in _destinos(puerta):
        m = await bot.send_message(chat_id=chat, message_thread_id=hilo, text=_render(puerta), reply_markup=_teclado(puerta))
        enviados.append({"chat": m.chat_id, "msg": m.message_id})
    PU.marcar(puerta["id"], telegram=enviados, tg_vista=_vista(puerta))


async def _sincronizar(bot, puerta: dict) -> None:
    if not puerta.get("telegram") or puerta.get("tg_vista") == _vista(puerta):
        return
    for t in puerta["telegram"]:
        try:
            await bot.edit_message_text(chat_id=t["chat"], message_id=t["msg"], text=_render(puerta), reply_markup=_teclado(puerta))
        except Exception as e:
            log.debug("hermes-seo: no se pudo editar %s: %s", t, e)
    PU.marcar(puerta["id"], tg_vista=_vista(puerta))


# ── botones y respuestas ────────────────────────────────────────────────────────────────────────────────────────────
def _pendientes() -> dict:
    return B.leer(B.home() / "pendientes.json", {}) or {}


def _pendiente(msg_id, valor=None, sacar: bool = False):
    d = _pendientes()
    if sacar:
        v = d.pop(str(msg_id), None)
        B.escribir(B.home() / "pendientes.json", d)
        return v
    d[str(msg_id)] = valor
    B.escribir(B.home() / "pendientes.json", d)
    return valor


async def _on_boton(update, context) -> None:
    _asegurar_bucle()
    q = update.callback_query
    _, verbo, gid = (q.data.split(":", 2) + ["", ""])[:3]
    persona, _ = PU.persona_de("telegram", q.from_user.id)
    if not persona:
        await q.answer("No estás autorizado para decidir esta puerta", show_alert=True)
        return
    try:
        puerta = PU.leer(gid)
    except B.Rechazo as e:
        await q.answer(str(e), show_alert=True)
        return
    if verbo == "deshacer":
        try:
            puerta = PU.deshacer(gid, persona)
        except B.Rechazo as e:
            await q.answer(str(e), show_alert=True)
            return
        await q.answer("Deshecho: vuelve a estar pendiente")
        await _sincronizar(context.bot, puerta)
        return
    opcion = next((o for o in puerta.get("opciones", []) if o["verbo"] == verbo), None)
    if not opcion or puerta.get("estado") != "abierta":
        await q.answer("Esta puerta ya está resuelta" if opcion else "Opción no válida", show_alert=True)
        return
    if opcion.get("texto"):
        from telegram import ForceReply
        await q.answer()
        m = await context.bot.send_message(
            chat_id=q.message.chat_id, message_thread_id=getattr(q.message, "message_thread_id", None),
            text=f"{opcion['etiqueta']}: responde a este mensaje explicando qué quieres, con tus palabras.",
            reply_markup=ForceReply(selective=True, input_field_placeholder="Qué cambiar o por qué…"))
        _pendiente(m.message_id, [gid, verbo, persona])
        return
    await q.answer(await _decidir(context.bot, gid, verbo, "", q.from_user, persona))


async def _decidir(bot, gid: str, verbo: str, texto: str, user, persona: str) -> str:
    try:
        puerta = PU.decidir(gid, verbo, texto, persona, "telegram", str(user.id), {"user": user.username or ""})
    except B.Rechazo as e:
        return str(e)
    await _sincronizar(bot, puerta)
    return f"Hecho. Tienes {PU.deshacer_s() // 60} min para deshacerlo."


async def _on_respuesta(update, context) -> None:
    m = update.message
    gid, verbo, persona = _pendiente(m.reply_to_message.message_id, sacar=True)
    if PU.persona_de("telegram", m.from_user.id)[0] != persona:
        await m.reply_text("Solo puede responder quien pulsó el botón.")
        return
    await m.reply_text(await _decidir(context.bot, gid, verbo, m.text.strip(), m.from_user, persona))


# ── lecciones entre webs ────────────────────────────────────────────────────────────────────────────────────────────
async def _avisar_lecciones(bot) -> None:
    L = _cargar("hseo_lecciones")
    avisadas = B.leer(B.home() / "lecciones-avisadas.json", {}) or {}
    from telegram import InlineKeyboardButton as Bt, InlineKeyboardMarkup as Mk
    for l in L.pendientes():
        clave = f"{l['id']}:{l['estado']}"
        if clave in avisadas:
            continue
        if l["estado"] == "propuesta":
            texto = (f"💡 Lección propuesta desde una de tus webs (etapa «{l['etapa']}»):\n\n{l['regla']}\n\n"
                     "Si la confirmas, se tendrá en cuenta en las demás webs.")
            kb = Mk([[Bt("✅ Confirmar", callback_data=f"hl:confirmar:{l['id']}"), Bt("🗑 Descartar", callback_data=f"hl:descartar:{l['id']}")]])
        else:
            texto = f"♻️ Esta lección ya se ha usado en {len(l['usos'])} webs. ¿Sigue sirviendo?\n\n{l['regla']}"
            kb = Mk([[Bt("♻️ Mantener", callback_data=f"hl:mantener:{l['id']}"), Bt("⌛ Caducar", callback_data=f"hl:caducar:{l['id']}")]])
        for chat, hilo in _destinos({"cliente": "__cartera__"}):
            await bot.send_message(chat_id=chat, message_thread_id=hilo, text=texto, reply_markup=kb)
        avisadas[clave] = B.ahora()
        B.escribir(B.home() / "lecciones-avisadas.json", avisadas)


async def _on_leccion(update, context) -> None:
    q = update.callback_query
    _, accion, lid = (q.data.split(":", 2) + ["", ""])[:3]
    persona, _ = PU.persona_de("telegram", q.from_user.id)
    if not persona:
        await q.answer("No estás autorizado", show_alert=True)
        return
    try:
        l = _cargar("hseo_lecciones").decidir(lid, accion, persona)
    except B.Rechazo as e:
        await q.answer(str(e), show_alert=True)
        return
    await q.answer({"confirmada": "Confirmada", "descartada": "Descartada", "caducada": "Caducada"}.get(l["estado"], "Hecho"))
    try:
        await q.edit_message_reply_markup(reply_markup=None)
    except Exception:
        pass


# ── el bucle: publicar, firmar, sincronizar ────────────────────────────────────────────────────────────────────
async def _vuelta() -> None:
    bot = _RT["app"].bot
    if time.time() - _RT.get("vueltas_t", 0) > 30:   # la verificación pidió cambios: vuelta automática (una vez)
        _RT["vueltas_t"] = time.time()
        try:
            for slug, eid, desde in await asyncio.to_thread(_cargar("hseo_encargos").vueltas_pendientes):
                log.info("hermes-seo: %s/%s vuelve a %s (la verificación pidió cambios)", slug, eid, desde)
        except Exception as e:   # noqa: BLE001 — nunca para el bucle de las puertas
            log.warning("hermes-seo: vueltas de verificación: %s", e)
    for p in PU.puertas(("abierta", "decidida", "error", "firmada")):
        if p["estado"] == "firmada" and p.get("tg_vista") == _vista(p):
            continue
        if p["estado"] in ("abierta", "decidida") and not p.get("telegram"):
            await asyncio.wait_for(_publicar(bot, p), 60)
            continue
        if p["estado"] == "decidida" and time.time() >= float(p.get("firmar_en") or 0) \
                and (p.get("decision") or {}).get("actor", {}).get("canal") != "local":
            try:
                p = await asyncio.to_thread(PU.firmar, p["id"])
            except B.Rechazo as e:
                log.warning("hermes-seo: no se pudo firmar %s: %s", p["id"], e)
            p = PU.leer(p["id"])
        await asyncio.wait_for(_sincronizar(bot, p), 60)


async def _bucle() -> None:
    log.info("hermes-seo: bucle en marcha")
    while True:
        await asyncio.sleep(5)
        try:
            await _vuelta()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("hermes-seo: error en una vuelta del bucle (sigue)")
        try:
            await _avisar_lecciones(_RT["app"].bot)
        except Exception:
            log.exception("hermes-seo: error al avisar de lecciones")
        try:
            B.escribir(B.home() / "latido.json", {"ts": B.ahora(), "pid": os.getpid()})
        except Exception:
            pass


def _asegurar_bucle() -> None:
    t = _RT.get("bucle")
    if t is None or t.done():
        _RT["bucle"] = asyncio.get_running_loop().create_task(_bucle())


# ── comandos ────────────────────────────────────────────────────────────────────────────────────────────────────────
def _persona_sesion():
    try:
        from gateway.session_context import get_session_env
        uid = get_session_env("HERMES_SESSION_USER_ID") or ""
    except Exception:
        uid = ""
    return (PU.persona_de("telegram", uid)[0], uid) if uid else (None, "")


def _cli(*args: str) -> str:
    import subprocess
    r = subprocess.run([sys.executable, str(AQUI / "hseo_cli.py"), *args], capture_output=True, text=True, timeout=120,
                       env={**os.environ, "HSEO_QUIEN": _persona_sesion()[0] or "telegram"})
    return (r.stdout if r.returncode == 0 else r.stderr).strip() or "Hecho."


async def _tema(slug: str, uid: str) -> str:
    """Tema «🧭 <web>» en el chat privado con el bot, enlazado con el encargado de la web (encargado.sh tema)."""
    bot = _RT["app"].bot
    try:
        cfg = C.leer(slug)
        tema = await bot.create_forum_topic(chat_id=int(uid), name=f"🧭 {cfg['nombre']}")
    except B.Rechazo as e:
        return str(e)
    except Exception as e:
        return (f"No pude crear el tema: {e}. Activa los temas del bot en @BotFather (Bot Settings → Threads Settings → "
                "Threaded Mode).")
    hilo = tema.message_thread_id
    proc = await asyncio.create_subprocess_exec("bash", str(_arnes() / "encargado.sh"), "tema", slug, str(uid), str(hilo),
                                                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    out, err = await proc.communicate()
    if proc.returncode != 0:
        return f"Creé el tema pero no pude enlazarlo: {(err or out).decode(errors='replace')[-300:]}"
    await bot.send_message(chat_id=int(uid), message_thread_id=hilo, text=(
        f"🧭 Aquí hablas con el encargado de {cfg['nombre']}: sabe en qué punto está todo, lanza el trabajo que le "
        "pidas y te trae aquí las decisiones. (Listo en un minuto: se reinicia el gateway para enlazar el tema.)"))
    import subprocess as sp
    sp.Popen(["bash", "-c", "sleep 8; hermes gateway restart >/dev/null 2>&1"], start_new_session=True,
             stdout=sp.DEVNULL, stderr=sp.DEVNULL)
    return f"Tema «🧭 {cfg['nombre']}» creado."


def _foto(info) -> str:
    """Lo que la coordinadora (default) y cada encargado (seo-p-<web>) saben al abrir una sesión."""
    perfil = str((info or {}).get("profile_name") or "")
    try:
        if perfil == "default":
            return "## hermes-seo: tus webs\n" + _cargar("hseo_cli").estado()[:3500]
        if perfil.startswith("seo-p-"):
            # una sesión de cron (el vigía) no «gasta» las novedades: las ve la conversación con la persona
            marcar = str((info or {}).get("platform") or "") != "cron"
            return _cargar("hseo_encargado").foto(perfil[len("seo-p-"):], marcar=marcar)[:3900]
    except Exception as e:
        log.warning("hermes-seo: foto de %s: %s", perfil, e)
    return ""


def register(ctx):
    # Hermes carga los plugins por perfil. En el perfil de un encargado (seo-p-<web>) solo va la foto del prompt:
    # el bucle de puertas, los botones y los comandos viven en el perfil principal (un solo dueño del bot).
    try:
        perfil = str(getattr(ctx, "profile_name", "") or "")
    except Exception:
        perfil = ""
    if perfil.startswith("seo-p-"):
        if hasattr(ctx, "register_system_prompt_section"):
            ctx.register_system_prompt_section("hermes-seo.foto", _foto, max_chars=4000)
        return

    def _wire(application, adapter):
        from telegram.ext import CallbackQueryHandler, MessageHandler, filters

        class _EsRespuesta(filters.MessageFilter):
            def filter(self, message):
                r = message.reply_to_message
                return bool(r and str(r.message_id) in _pendientes())

        _RT["app"] = application
        application.add_handler(CallbackQueryHandler(_on_boton, pattern=rf"^{PREFIJO}:"))
        application.add_handler(CallbackQueryHandler(_on_leccion, pattern=r"^hl:"))
        application.add_handler(MessageHandler(filters.TEXT & _EsRespuesta(), _on_respuesta))
        _asegurar_bucle()

    def _cmd_seo(raw: str = "") -> str:
        return _cli("estado", *raw.split()[:1])

    def _cmd_puertas(raw: str = "") -> str:
        abiertas = PU.puertas(("abierta",))
        for p in abiertas:   # el bucle las vuelve a publicar con sus botones
            PU.marcar(p["id"], telegram=None, tg_vista=None)
        return f"Te reenvío {len(abiertas)} decisión(es) pendiente(s)." if abiertas else "No hay nada pendiente de decidir."

    async def _cmd_tema(raw: str = "") -> str:
        persona, uid = _persona_sesion()
        if not persona or not raw.strip():
            return "Uso: /seo_tema <web> (solo una persona autorizada)"
        return await _tema(raw.split()[0], uid)

    def _cmd_pausar(raw: str = "") -> str:
        return _cli("pausar", raw.split()[0] if raw.split() else "todo") if _persona_sesion()[0] else "Solo una persona autorizada."

    def _cmd_reanudar(raw: str = "") -> str:
        return _cli("reanudar", raw.split()[0] if raw.split() else "todo") if _persona_sesion()[0] else "Solo una persona autorizada."

    ctx.register_telegram_handler(_wire)
    # args_hint siempre entre [ ]: Hermes deja fuera del menú las órdenes cuya ayuda empieza por «<»
    ctx.register_command("seo", _cmd_seo, description="Estado del SEO de tus webs", args_hint="[web]")
    ctx.register_command("seo_puertas", _cmd_puertas, description="Decisiones SEO pendientes")
    ctx.register_command("seo_tema", _cmd_tema, description="Tema para hablar con el encargado de una web", args_hint="[web]")
    ctx.register_command("seo_pausar", _cmd_pausar, description="Pausa una web (o todo)", args_hint="[web|todo]")
    ctx.register_command("seo_reanudar", _cmd_reanudar, description="Reanuda una web (o todo)", args_hint="[web|todo]")
    if hasattr(ctx, "register_system_prompt_section"):
        ctx.register_system_prompt_section("hermes-seo.foto", _foto, max_chars=4000)
