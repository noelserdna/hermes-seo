"""Ejecuta UNA etapa de un encargo (lo llama etapa.sh desde la tarjeta del kanban). Como etapa.sh de hermes-sdd:
elige ejecutor y modelo, monta el encargo para el agente, lo lanza, comprueba que dejó su salida, lo apunta y, si es la
última etapa, abre la puerta de la pipeline.

  hseo_etapa.py <slug> <encargo> <etapa>

Última línea de stdout: JSON {outcome: done|failed|scheduled|busy, reason, resumen, puerta, run, cost_usd, minutes}.
La estación solo traduce `outcome` a una acción del kanban.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
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
M = _cargar("hseo_modelos")


def contexto(slug: str, etapa: str | None = None) -> str:
    """Lo que todo agente sabe del cliente (el plugin lo pone también en el prompt de los perfiles)."""
    cfg = C.leer(slug)
    neg = cfg.get("negocio") or {}
    pol = cfg.get("politicas") or {}
    wiki = C.carpeta(slug) / "wiki"
    l = [f"# Cliente: {cfg['nombre']} ({cfg['url']})", "",
         f"- Nombre corto (para las herramientas: --cliente): {slug}",
         f"- Herramientas de datos: {PL.raiz() / 'herramientas'} (cada una con --cliente {slug}; `--help` para el uso)",
         f"- Idioma: {cfg['idioma']} · mercados: {', '.join(m['pais'] for m in cfg['mercados'])} · zona: {cfg['zona_horaria']}",
         f"- Estado de la web: {cfg['estado_web']} · publica con: {cfg['capacidades']['publicacion'].get('adaptador')}",
         f"- Capacidades: {', '.join(sorted(C.capacidades(cfg)))}"]
    if neg.get("publico"):
        l.append(f"- Público: {neg['publico']}")
    if neg.get("voz"):
        l.append(f"- Voz: {neg['voz']}")
    if neg.get("objetivo"):
        l.append(f"- Objetivo: {neg['objetivo']}")
    if cfg.get("competidores"):
        l.append(f"- Competidores: {', '.join(cfg['competidores'])}")
    if pol.get("congelado_hasta"):
        l.append(f"- Sin piezas nuevas hasta {pol['congelado_hasta']}")
    l += ["", f"Memoria del cliente (wiki): {wiki} (empieza por index.md; enlaza, no copies).",
          f"Datos: {C.carpeta(slug) / 'datos'}"]
    lecciones = _lecciones(slug, etapa)
    if lecciones:
        l += ["", "## Lecciones de otros proyectos (confirmadas por una persona)", *[f"- {x}" for x in lecciones]]
    return "\n".join(l) + "\n"


def _lecciones(slug: str, etapa: str | None) -> list:
    """Lecciones confirmadas de otras webs: las de la etapa (y se anota el uso) o, sin etapa, todas sin anotar."""
    try:
        return _cargar("hseo_lecciones").para_cliente(slug, etapa, anotar=etapa is not None)
    except Exception:
        return []


PROMPT = """Harness mode (hermes-seo). You are doing ONE stage of a pipeline for a website client.
Stage: {etapa} — {titulo}
Skill to follow: {skill}{ruta_skill}
Working folder: {dir} (work only here; read brief.md and contexto-cliente.md first)
Earlier stages left: {previas}
Write your result to: {salida}
Write for people in the client's language ({idioma}).
Do NOT publish, deploy, send messages or change the client's configuration: publishing and other irreversible steps
are decided by a person at a gate after this pipeline. If something blocks you, write why in {salida} and stop.
End your reply with ONE short line summarising the result."""


def ejecutar(slug: str, eid: str, etapa: str) -> dict:
    enc = E.leer(slug, eid)
    d = E.carpeta(slug, eid)
    cfg = C.leer(slug)
    if (cfg.get("politicas") or {}).get("pausado") or (B.home() / "pausa").exists():
        return {"outcome": "scheduled", "reason": "en pausa", "reset_at": int(time.time()) + 3600}
    cuota = B.leer(B.home() / "cuota.json", {}) or {}
    if float(cuota.get("reset_at") or 0) > time.time():
        return {"outcome": "scheduled", "reason": "cuota de Claude agotada", "reset_at": cuota["reset_at"]}
    p = PL.cargar(enc["pipeline"], slug)
    s = next((x for x in p["etapas"] if x["id"] == etapa), None)
    if not s or etapa not in [x["id"] for x in enc["etapas"]]:
        return {"outcome": "failed", "reason": f"la etapa {etapa} no es de este encargo"}
    orden = [x["id"] for x in enc["etapas"]]
    salidas = {x["id"]: x.get("salida") for x in p["etapas"]}
    previas = [f"{salidas[i]} ({i})" for i in orden[:orden.index(etapa)] if salidas.get(i) and (d / salidas[i]).exists()]
    previas += [f"{h} (from {enc['origen']})" for h in enc.get("heredados") or [] if (d / h).exists()]
    salida = s.get("salida") or f"{etapa}.md"
    (d / "contexto-cliente.md").write_text(contexto(slug, etapa))
    ejecutor = (cfg.get("ejecutores") or {}).get(etapa) or s.get("ejecutor", "hermes")
    arnes = PL.raiz()
    propia = C.carpeta(slug) / "extensiones" / "skills" / s["skill"] / "SKILL.md"   # las de la web mandan
    skill_md = propia if propia.exists() else arnes / "skills" / s["skill"] / "SKILL.md"
    if ejecutor == "claude" and not skill_md.exists():
        return {"outcome": "failed", "reason": f"no encuentro la skill {s['skill']} (ni en la web ni en el plugin)"}
    titulo = next(x["titulo"] for x in enc["etapas"] if x["id"] == etapa)
    prompt = PROMPT.format(etapa=etapa, titulo=titulo, skill=s["skill"], dir=d, salida=salida, idioma=cfg["idioma"],
                           previas=", ".join(previas) or "nothing (first stage)",
                           ruta_skill=f" (read {skill_md})" if ejecutor == "claude" else "")
    feedback = d / ".estado" / f"feedback-{etapa}.txt"
    if feedback.exists():
        prompt += "\n\nWhat the person asked to change last time (apply it):\n" + feedback.read_text()[:4000]
    fb_verif = d / ".estado" / f"feedback-verificacion-{etapa}.txt"
    if fb_verif.exists():
        prompt += ("\n\nThe fact-check of your previous version asked for changes. Apply EVERY mandatory change below "
                   "(and keep what was right):\n" + fb_verif.read_text()[:4000])
    modelo = M.para(etapa, ejecutor, slug, s["perfil"])
    antes = (d / salida).stat().st_mtime if (d / salida).exists() else 0
    env = {**os.environ, "HERMES_SEO_HOME": str(B.home())}
    if ejecutor == "claude":   # Claude Code con la sesión de la cuenta (si el sistema la guarda en los secretos)
        sec = C.secretos(slug)
        if sec.get("CLAUDE_CODE_OAUTH_TOKEN"):
            env["CLAUDE_CODE_OAUTH_TOKEN"] = sec["CLAUDE_CODE_OAUTH_TOKEN"]
        extra = (cfg.get("ejecutor_claude") or {})
        if extra.get("herramientas_extra"):   # p. ej. git, gh o el build de la web, si una etapa propia los necesita
            env["HSEO_CLAUDE_TOOLS_EXTRA"] = str(extra["herramientas_extra"])
        if extra.get("directorios"):   # carpetas fuera del encargo en las que puede trabajar (el repo, sus worktrees)
            env["HSEO_CLAUDE_DIRS"] = ":".join(os.path.expanduser(str(x)) for x in extra["directorios"])
        for k in extra.get("secretos", []):   # claves del cliente que esa etapa necesita (p. ej. GH_TOKEN)
            if sec.get(k):
                env["HSEO_PASAR_" + k] = sec[k]
    ejecutores = Path(os.environ.get("HSEO_EJECUTORES") or arnes / "executors")   # las pruebas ponen los suyos
    if not (ejecutores / f"{ejecutor}.sh").exists():
        return {"outcome": "failed", "reason": f"no existe el ejecutor «{ejecutor}»"}
    cmd = ["bash", str(ejecutores / f"{ejecutor}.sh"), str(d), f"{etapa}", prompt, modelo, s["perfil"], s["skill"]]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env)
    try:
        res = json.loads((r.stdout.strip().splitlines() or ["{}"])[-1])
    except ValueError:
        res = {"outcome": "failed", "reason": f"el ejecutor no devolvió JSON: {r.stdout[-200:]} {r.stderr[-200:]}"}
    if res.get("outcome") == "done":
        if not (d / salida).exists() or (d / salida).stat().st_mtime <= antes:
            res = {**res, "outcome": "failed", "reason": f"la etapa terminó sin dejar {salida}"}
    return {**res, "salida": salida, "ejecutor": ejecutor, "modelo": modelo}


def fin(slug: str, eid: str, etapa: str, res: dict, t0: float) -> dict:
    enc = E.leer(slug, eid)
    ultima = enc["etapas"][-1]["id"] == etapa
    res.setdefault("resumen", "")
    s = next((x for x in PL.cargar(enc["pipeline"], slug)["etapas"] if x["id"] == etapa), {})
    if res.get("outcome") == "done" and s.get("si_cambios") and int(enc.get("vueltas_verificacion") or 0) == 0:
        d = E.carpeta(slug, eid)
        f = d / (s.get("salida") or f"{etapa}.md")
        if _cargar("hseo_revision")._veredicto(f) == "CAMBIOS":
            # una sola vuelta automática: el texto vuelve a la etapa indicada con los cambios pedidos, sin pasar por
            # la persona; las tarjetas siguientes no deben arrancar (la tarjeta se da por fallida y la rehace el bucle)
            (d / f"{f.stem}-1{f.suffix}").write_text(f.read_text(errors="replace"))
            enc.update(estado="en-vuelta", vueltas_verificacion=1,
                       vuelta_pendiente={"desde": s["si_cambios"], "texto": f.read_text(errors="replace")[:4000]})
            E.guardar(slug, enc)
            res = {**res, "outcome": "failed", "reason": f"la verificación pidió cambios: vuelve a {s['si_cambios']} (una vez)",
                   "vuelta": s["si_cambios"]}
            B.anotar(C.carpeta(slug) / "etapas.jsonl", {
                "ts": B.ahora(), "encargo": eid, "pipeline": enc["pipeline"], "etapa": etapa,
                "tarjeta": (enc.get("tarjetas") or {}).get(etapa, ""), "resultado": "cambios", "motivo": res["reason"],
                "ejecutor": res.get("ejecutor", ""), "modelo": res.get("modelo", ""),
                "minutos": round((time.time() - t0) / 60, 1), "coste_usd": res.get("cost_usd", 0), "puerta": ""})
            return res
    if res.get("outcome") == "done" and ultima:
        # una puerta solo existe si aprobarla ejecuta algo; si no, es un informe: se guarda y sale en el parte
        decide = bool(enc.get("puerta")) and str((enc.get("puerta") or {}).get("al_aprobar", "nada")) != "nada"
        enc["estado"] = "en-puerta" if decide else "hecho"
        if enc.get("puerta") and not decide:
            enc["informe"] = True
        E.guardar(slug, enc)
        if decide:
            try:
                g = _cargar("hseo_puertas").abrir(slug, eid)
                res["puerta"] = g["id"]
            except Exception as x:   # la etapa hizo su trabajo: el fallo al abrir la puerta lo ve el vigía
                res["puerta_error"] = str(x)[:300]
    elif res.get("outcome") == "failed":
        enc["estado"] = "parado"
        E.guardar(slug, enc)
    B.anotar(C.carpeta(slug) / "etapas.jsonl", {
        "ts": B.ahora(), "encargo": eid, "pipeline": enc["pipeline"], "etapa": etapa,
        "tarjeta": (enc.get("tarjetas") or {}).get(etapa, ""), "resultado": res.get("outcome"),
        "motivo": res.get("reason", ""), "ejecutor": res.get("ejecutor", ""), "modelo": res.get("modelo", ""),
        "minutos": round((time.time() - t0) / 60, 1), "coste_usd": res.get("cost_usd", 0),
        "puerta": res.get("puerta", "")})
    return res


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if len(argv) != 3:
        print(json.dumps({"outcome": "failed", "reason": "uso: hseo_etapa.py <slug> <encargo> <etapa>"}))
        return 0
    t0 = time.time()
    try:
        res = ejecutar(*argv)
    except B.Rechazo as e:
        res = {"outcome": "failed", "reason": str(e)}
    try:
        res = fin(*argv, res, t0)
    except B.Rechazo as e:
        res = {**res, "outcome": "failed", "reason": str(e)}
    print(json.dumps(res, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
