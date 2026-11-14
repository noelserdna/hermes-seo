"""Plugin de Telegram con bot y updates falsos (sin red): publicar en el tema de la web, autorización, motivo por
respuesta, deshacer, firma al acabar la ventana, Jev en el bucle, comandos y la foto en el prompt."""
import asyncio, importlib.util, json, os, sys, tempfile
from pathlib import Path
from types import SimpleNamespace as NS

ROOT = Path(__file__).resolve().parent.parent
T = Path(tempfile.mkdtemp()); HOME = T / "home"
os.environ.update(HERMES_SEO_HOME=str(HOME), HERMES_SEO_DESHACER_S="0", TELEGRAM_HOME_CHANNEL="111")
spec = importlib.util.spec_from_file_location("hseo_plugin", ROOT / "plugin/hermes-seo/__init__.py")
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
C, PU = m.C, m.PU
fallos = 0
def ok(c, t):
    global fallos
    print(("ok   " if c else "FAIL ") + t); fallos += (not c)

class Bot:
    def __init__(s): s.enviados, s.editados, s.n = [], [], 100
    async def send_message(s, chat_id, text, reply_markup=None, message_thread_id=None, **k):
        s.n += 1; s.enviados.append(NS(chat=chat_id, hilo=message_thread_id, text=text, kb=reply_markup)); return NS(chat_id=chat_id, message_id=s.n)
    async def edit_message_text(s, chat_id, message_id, text, reply_markup=None): s.editados.append(NS(text=text, kb=reply_markup))

class Query:
    def __init__(s, data, uid): s.data, s.from_user, s.id = data, NS(id=uid, username="u"), "cb"; s.message = NS(chat_id=111, message_id=7, message_thread_id=55); s.respuestas = []
    async def answer(s, text=None, show_alert=False): s.respuestas.append(text)

def botones(kb): return [b.callback_data for f in kb.inline_keyboard for b in f] if kb else []

C.alta("web", "web.com")
C.config("web", "telegram", {"chat_id": "111", "thread_id": "55"})
(HOME / "aprobadores.json").write_text(json.dumps({"ana": {"nombre": "Ana", "canales": {"telegram": "111"}, "clientes": ["*"]}}))
bot = Bot(); ctx = NS(bot=bot)

async def main():
    m._RT["app"] = NS(bot=bot); m._RT["bucle"] = asyncio.get_running_loop().create_future()
    g = PU.abrir("web", tipo="decision", titulo="📊 Métricas", texto="3 propuestas")["id"]
    await m._vuelta()
    e = bot.enviados[-1]
    ok(e.chat == 111 and e.hilo == 55, "la puerta se publica en el tema de la web")
    ok(botones(e.kb) == [f"hs:acepto:{g}", f"hs:cambios:{g}", f"hs:rechazo:{g}"], f"botones con prefijo hs: ({botones(e.kb)})")
    q = Query(f"hs:acepto:{g}", 999); await m._on_boton(NS(callback_query=q), ctx)
    ok("No estás autorizado" in (q.respuestas[-1] or ""), "rechaza a quien no es aprobador")
    q = Query(f"hs:cambios:{g}", 111); await m._on_boton(NS(callback_query=q), ctx)
    pend = m._pendientes(); ok(len(pend) == 1 and bot.enviados[-1].hilo == 55, "«Cambios» pide el motivo en el mismo tema")
    pid = int(next(iter(pend)))
    msg = NS(text="Menos propuestas", from_user=NS(id=111, username="u"), message_id=9, reply_to_message=NS(message_id=pid))
    async def rep(t): msg.r = t
    msg.reply_text = rep
    await m._on_respuesta(NS(message=msg), ctx)
    p = PU.leer(g)
    ok(p["estado"] == "decidida" and p["decision"]["texto"] == "Menos propuestas" and p["decision"]["actor"]["id"] == "111",
       "la respuesta crea la decisión con la identidad de Telegram")
    ok(botones(bot.editados[-1].kb) == [f"hs:deshacer:{g}"], "decidida: solo queda ↩ Deshacer")
    q = Query(f"hs:deshacer:{g}", 111); await m._on_boton(NS(callback_query=q), ctx)
    ok(PU.leer(g)["estado"] == "abierta", "Deshacer la reabre")
    q = Query(f"hs:rechazo:{g}", 111); await m._on_boton(NS(callback_query=q), ctx)
    pid = int(next(iter(m._pendientes())))
    msg.reply_to_message = NS(message_id=pid); msg.text = "No toca"
    await m._on_respuesta(NS(message=msg), ctx)
    await m._vuelta()
    p = PU.leer(g)
    ok(p["estado"] == "firmada" and p["resultado"] == "descartado" and p["firma"] == "Ana (telegram)", "pasada la ventana, el bucle firma")
    ok("✅ Ana (telegram): descartado" in bot.editados[-1].text, "el mensaje enseña el resultado")
    n = len(bot.editados); await m._vuelta()
    ok(len(bot.editados) == n, "una puerta firmada y al día no se vuelve a tocar")

    # Jev en el bucle (respuesta simulada)
    PU.poner_modo("auto", "web")
    PU.consultar_jev = lambda p: {"choice": "acepto", "p": 0.93, "modelo": "jev-latest"}
    g2 = PU.abrir("web", tipo="decision", titulo="📊 Otra", texto="x")["id"]
    os.environ["HERMES_SEO_DESHACER_S"] = "60"
    await m._vuelta()
    p = PU.leer(g2)
    ok(p["estado"] == "decidida" and p["decision"]["actor"]["canal"] == "jev", "Jev decide en auto si está seguro")
    ok("Ha decidido Jev" in bot.enviados[-1].text and botones(bot.enviados[-1].kb) == [f"hs:deshacer:{g2}"],
       "se publica ya decidida, con ↩ Deshacer")
    q = Query(f"hs:deshacer:{g2}", 111); await m._on_boton(NS(callback_query=q), ctx)
    p = PU.leer(g2); ok(p["estado"] == "abierta" and p.get("jev_vetado"), "deshacer a Jev le veta en esa puerta")
    PU.consultar_jev = lambda p: {"choice": "acepto", "p": 0.5}
    g3 = PU.abrir("web", tipo="decision", titulo="📊 Dudosa", texto="x")["id"]
    await m._vuelta()
    p = PU.leer(g3); ok(p["estado"] == "abierta" and "no está seguro" in p["jev"]["motivo"], "si Jev duda, decide la persona")
    ok("Jev aprobaría" in bot.enviados[-1].text, "y la puerta lleva su consejo")

    # comandos y foto
    cmds, secciones = {}, {}
    ctx_h = NS(register_telegram_handler=lambda f: None,
               register_command=lambda n, f, **k: cmds.__setitem__(n, (f, k)),
               register_system_prompt_section=lambda i, f, **k: secciones.__setitem__(i, f))
    m.register(ctx_h)
    ok(set(cmds) == {"seo", "seo_puertas", "seo_jev", "seo_tema", "seo_pausar", "seo_reanudar"}, f"comandos ({sorted(cmds)})")
    ok(all(not k.get("args_hint", "").startswith("<") for _, k in cmds.values()), "ninguna ayuda empieza por «<» (saldría del menú)")
    ok("web.com" in cmds["seo"][0](""), "/seo da el estado")
    foto = secciones["hermes-seo.foto"]
    ok("tus webs" in foto({"profile_name": "default"}), "la coordinadora ve sus webs en el prompt")
    f = foto({"profile_name": "seo-p-web"})
    ok("Cliente: web" in f and "Desde tu última sesión" in f, "el encargado ve la foto de su web")
    ok(foto({"profile_name": "otro"}) == "", "otros perfiles, nada")

asyncio.run(main())
sys.exit(1 if fallos else 0)
