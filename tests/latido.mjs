// Worker del latido: autorización, avisos solo al cambiar el estado (caída y recuperación).
import * as W from "../latido/worker.js";
let fallos = 0; const ok = (c, m) => { console.log((c ? "ok   " : "FAIL ") + m); if (!c) fallos = 1; };
const kv = new Map(); const enviados = [];
const env = { LATIDO_SECRETO: "s3", TELEGRAM_BOT_TOKEN: "t", TELEGRAM_CHAT_ID: "1", MINUTOS: "15",
  LATIDO: { get: async (k, t) => kv.has(k) ? (t === "json" ? JSON.parse(kv.get(k)) : kv.get(k)) : null, put: async (k, v) => kv.set(k, v) } };
globalThis.fetch = async (url, o) => { enviados.push(JSON.parse(o.body).text); return new Response("{}"); };
const post = (auth, body) => W.default.fetch(new Request("https://x/latido", { method: "POST", headers: { authorization: auth }, body: JSON.stringify(body) }), env);
ok((await post("Bearer malo", {})).status === 401, "sin el secreto, 401");
ok((await post("Bearer s3", { gateway: "active", disco: 31 })).status === 200, "con el secreto, se guarda");
let r = await W.revisar(env); ok(r.lista.length === 0 && !r.aviso && enviados.length === 0, "todo bien: no escribe");
kv.set("ultimo", JSON.stringify({ ...JSON.parse(kv.get("ultimo")), gateway: "failed", reiniciado: true }));
r = await W.revisar(env); ok(r.aviso && /gateway.*no volvió/.test(enviados.at(-1)), "gateway caído tras reiniciarlo: avisa");
kv.set("ultimo", JSON.stringify({ ...JSON.parse(kv.get("ultimo")), gateway: "active" })); await W.revisar(env);
r = await W.revisar(env, Date.now() + 20 * 60000); ok(r.aviso && enviados.at(-1).startsWith("🚨") && /no da señales/.test(enviados.at(-1)), "20 min sin latido: avisa de caída");
r = await W.revisar(env, Date.now() + 25 * 60000); ok(!r.aviso, "la caída no se repite cada 5 min");
await post("Bearer s3", { gateway: "active", disco: 31 }); r = await W.revisar(env); ok(r.aviso && enviados.at(-1).startsWith("✅"), "al volver el latido: avisa de la recuperación");
process.exit(fallos);
