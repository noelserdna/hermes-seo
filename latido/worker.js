// Latido de hermes-seo: el servidor manda un latido cada 5 min; si deja de llegar, o llega con el gateway caído o el
// disco lleno, este Worker avisa por Telegram DESDE FUERA del servidor (una vez al caer y otra al recuperarse).
// KV: "ultimo" (último latido) y "estado" (lo último que se avisó). Secretos: LATIDO_SECRETO, TELEGRAM_BOT_TOKEN.
// Variables: TELEGRAM_CHAT_ID, NOMBRE (cómo se llama el servidor en los avisos), MINUTOS (sin latido = caído).

const json = (d, s = 200) => new Response(JSON.stringify(d), { status: s, headers: { "content-type": "application/json" } });

function igual(a, b) {
  if (a.length !== b.length) return false;
  let r = 0;
  for (let i = 0; i < a.length; i++) r |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return r === 0;
}

export function problemas(ultimo, ahora, minutos) {
  if (!ultimo) return ["no ha llegado ningún latido todavía"];
  const out = [];
  const min = Math.round((ahora - ultimo.recibido) / 60000);
  if (min > minutos) return [`no da señales desde hace ${min} min (servidor caído, sin red o sin cron)`];
  if (ultimo.gateway !== "active") out.push(`el gateway de Hermes está «${ultimo.gateway}»${ultimo.reiniciado ? " y no volvió tras reiniciarlo" : ""}`);
  if (ultimo.disco >= 90) out.push(`el disco está al ${ultimo.disco} %`);
  return out;
}

async function avisar(env, texto) {
  const token = String(env.TELEGRAM_BOT_TOKEN || "").trim();   // un salto de línea al guardar el secreto rompe la URL
  const r = await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
    method: "POST", headers: { "content-type": "application/json" },
    body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: texto, disable_web_page_preview: true }),
  });
  const cuerpo = r.ok ? "" : (await r.text()).slice(0, 200);
  if (!r.ok) console.log("telegram", r.status, cuerpo);
  return { ok: r.ok, status: r.status, error: cuerpo };
}

export async function revisar(env, ahora = Date.now()) {
  const ultimo = await env.LATIDO.get("ultimo", "json");
  const lista = problemas(ultimo, ahora, Number(env.MINUTOS || 15));
  const texto = lista.join(" · ");
  const clave = texto.replace(/\d+/g, "#");   // el tipo de problema, no sus cifras: que no se repita cada 5 min
  const antes = (await env.LATIDO.get("estado")) || "";
  if (clave === antes) return { lista, aviso: false };
  const nombre = env.NOMBRE || "el servidor de Hermes";
  if (clave) await avisar(env, `🚨 ${nombre}: ${texto}.\n\nAviso desde fuera del servidor (Cloudflare). Te escribo otra vez cuando se recupere.`);
  else await avisar(env, `✅ ${nombre} vuelve a estar bien.`);
  await env.LATIDO.put("estado", clave);
  return { lista, aviso: true };
}

export default {
  async fetch(req, env) {
    const url = new URL(req.url);
    if (url.pathname === "/latido" && req.method === "POST") {
      const auth = req.headers.get("authorization") || "";
      if (!env.LATIDO_SECRETO || !igual(auth, `Bearer ${env.LATIDO_SECRETO}`)) return json({ error: "no autorizado" }, 401);
      let d = {};
      try { d = await req.json(); } catch { return json({ error: "JSON no válido" }, 400); }
      const ultimo = { recibido: Date.now(), gateway: String(d.gateway || "?").slice(0, 20),
                       disco: Number(d.disco) || 0, reiniciado: Boolean(d.reiniciado) };
      await env.LATIDO.put("ultimo", JSON.stringify(ultimo));
      return json({ ok: true });
    }
    if (url.pathname === "/prueba" && req.method === "POST") {   // diagnóstico: manda un aviso de prueba y dice qué respondió Telegram
      const auth = req.headers.get("authorization") || "";
      if (!env.LATIDO_SECRETO || !igual(auth, `Bearer ${env.LATIDO_SECRETO}`)) return json({ error: "no autorizado" }, 401);
      return json(await avisar(env, `🧪 ${env.NOMBRE || "hermes-latido"}: prueba del aviso externo (todo bien, no hagas nada).`));
    }
    return new Response("hermes-latido", { status: 404 });
  },
  async scheduled(_ev, env, ctx) {
    ctx.waitUntil(revisar(env));
  },
};
