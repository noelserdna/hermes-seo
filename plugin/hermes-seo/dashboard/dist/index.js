// hermes-seo — pestaña «SEO» del panel web de Hermes (canal dashboard).
// Sin build: IIFE con el SDK del panel (window.__HERMES_PLUGIN_SDK__). La API está en plugin_api.py.
(function () {
  "use strict";
  const SDK = window.__HERMES_PLUGIN_SDK__;
  const { React } = SDK;
  const { useState, useEffect, useCallback } = SDK.hooks;
  const { Button, Badge, Input } = SDK.components;
  const h = React.createElement;
  const API = "/api/plugins/hermes-seo";
  const get = (r) => SDK.fetchJSON(API + r);
  const post = (r, c) => SDK.fetchJSON(API + r, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(c || {}) });
  const BORDE = "1px solid var(--color-border)";
  const caja = { border: BORDE, borderRadius: 8, padding: 14, marginBottom: 12 };
  const tenue = { color: "var(--color-muted-foreground)", fontSize: 13 };
  const num = (n) => (n == null ? "—" : Number(n).toLocaleString("es-ES"));

  function usarDatos(ruta, cada) {
    const [datos, setDatos] = useState(null);
    const [error, setError] = useState("");
    const cargar = useCallback(() => get(ruta).then((d) => { setDatos(d); setError(""); }).catch((e) => setError(String(e.message || e))), [ruta]);
    useEffect(() => { cargar(); if (!cada) return; const t = setInterval(cargar, cada); return () => clearInterval(t); }, [cargar, cada]);
    return [datos, error, cargar];
  }

  function Disco() {
    const [s] = usarDatos("/sistema", 60000);
    if (!s || !s.disco || !s.disco.length) return null;
    return h("div", { style: { display: "flex", gap: 8, flexWrap: "wrap", marginBottom: 12 } }, s.disco.map((d) =>
      h(Badge, { key: d.punto, variant: d.aviso ? "destructive" : "outline" },
        (d.aviso ? "⚠️ " : "💾 ") + "Disco" + (s.disco.length > 1 ? " " + d.punto : "") + ": " + d.usado_pct + " % usado · " +
        String(d.libres_gb).replace(".", ",") + " GB libres de " + Math.round(d.total_gb))));
  }

  function Cartera() {
    const [webs, error] = usarDatos("/webs", 15000);
    if (error) return h("p", { style: tenue }, error);
    if (!webs) return h("p", { style: tenue }, "Cargando…");
    if (!webs.length) return h("div", null, h(Disco), h("p", null, "Aún no hay ninguna web. Pídeselo a la coordinadora: «da de alta mi web …»."));
    return h("div", null, h(Disco), webs.map((w) => h("div", { key: w.slug, style: caja },
      h("div", { style: { display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" } },
        h("strong", null, w.nombre), h("a", { href: w.url, target: "_blank", rel: "noreferrer", style: tenue }, w.url),
        h(Badge, { variant: "outline" }, "web " + w.estado_web), h(Badge, { variant: "outline" }, "publica: " + w.publica),
        h(Badge, { variant: w.jev === "humano" ? "secondary" : "default" }, "Jev: " + w.jev),
        w.pausada ? h(Badge, { variant: "destructive" }, "en pausa") : null,
        w.puertas ? h(Badge, null, "🚪 " + w.puertas) : null),
      h("div", { style: { ...tenue, marginTop: 6 } }, "Puede: " + (w.capacidades.join(", ") || "nada configurado aún")),
      w.encargos.length
        ? h("ul", { style: { margin: "8px 0 0 18px" } }, w.encargos.map((e) => h("li", { key: e.id }, e.nombre + " · " + e.estado)))
        : h("div", { style: { ...tenue, marginTop: 6 } }, "Nada en marcha."))));
  }

  function Puerta({ p, recargar }) {
    const [texto, setTexto] = useState("");
    const [msg, setMsg] = useState("");
    const hacer = (ruta, cuerpo) => post(ruta, cuerpo).then(() => { setMsg(""); recargar(); }).catch((e) => setMsg(String(e.message || e)));
    return h("div", { style: caja },
      h("strong", null, p.titulo),
      h("pre", { style: { whiteSpace: "pre-wrap", fontFamily: "inherit", margin: "8px 0", maxHeight: 320, overflow: "auto" } }, p.texto),
      p.jev ? h("p", { style: tenue }, p.jev) : null,
      p.estado === "abierta" ? h("div", null,
        h(Input, { placeholder: "Motivo (para pedir cambios, rechazar o descartar)", value: texto, onChange: (e) => setTexto(e.target.value), style: { marginBottom: 8 } }),
        h("div", { style: { display: "flex", gap: 8, flexWrap: "wrap" } }, p.opciones.map((o) => h(Button, {
          key: o.verbo, size: "sm", variant: o.texto ? "outline" : "default", disabled: o.texto && !texto.trim(),
          onClick: () => hacer("/decidir/" + p.id, { verbo: o.verbo, texto }) }, o.etiqueta))))
      : p.estado === "decidida" ? h("div", { style: { display: "flex", gap: 8, alignItems: "center" } },
        h("span", null, "🕒 Decidido por " + p.decidio + ": «" + p.decision.verbo + "». Se ejecuta al acabar la ventana."),
        h(Button, { size: "sm", variant: "outline", onClick: () => hacer("/deshacer/" + p.id) }, "↩ Deshacer"))
      : h("p", { style: { color: "var(--color-destructive)" } }, "⚠️ " + (p.error || p.estado)),
      msg ? h("p", { style: { color: "var(--color-destructive)" } }, msg) : null);
  }

  function Decisiones() {
    const [ps, error, recargar] = usarDatos("/puertas", 10000);
    if (error) return h("p", { style: tenue }, error);
    if (!ps) return h("p", { style: tenue }, "Cargando…");
    if (!ps.length) return h("p", null, "No hay nada pendiente de decidir.");
    return h("div", null, ps.map((p) => h(Puerta, { key: p.id, p, recargar })));
  }

  function Grafico({ serie }) {
    if (!serie || serie.length < 2) return null;
    const W = 640, H = 140, max = Math.max(1, ...serie.map((d) => d.clics));
    const x = (i) => (i / (serie.length - 1)) * (W - 20) + 10;
    const y = (v) => H - 10 - (v / max) * (H - 30);
    const linea = serie.map((d, i) => (i ? "L" : "M") + x(i).toFixed(1) + " " + y(d.clics).toFixed(1)).join(" ");
    return h("svg", { viewBox: `0 0 ${W} ${H}`, style: { width: "100%", maxWidth: W, height: "auto" }, role: "img",
      "aria-label": "Clics por día de los últimos " + serie.length + " días" },
      h("path", { d: linea, fill: "none", stroke: "var(--color-primary)", strokeWidth: 2 }),
      h("text", { x: 10, y: 14, fontSize: 11, fill: "currentColor" }, "Clics por día (máx. " + num(max) + ")"),
      h("text", { x: 10, y: H - 1, fontSize: 10, fill: "currentColor" }, serie[0].fecha),
      h("text", { x: W - 10, y: H - 1, fontSize: 10, fill: "currentColor", textAnchor: "end" }, serie[serie.length - 1].fecha));
  }

  function Dato({ nombre, ahora, antes, inverso, sufijo }) {
    const d = ahora != null && antes != null ? ahora - antes : null;
    const bueno = d == null || d === 0 ? null : (inverso ? d < 0 : d > 0);
    return h("div", { style: { ...caja, minWidth: 140, marginBottom: 0 } },
      h("div", { style: tenue }, nombre),
      h("div", { style: { fontSize: 22, fontWeight: 600 } }, num(ahora) + (sufijo || "")),
      d == null ? null : h("div", { style: { fontSize: 12, color: bueno == null ? "inherit" : bueno ? "var(--color-primary)" : "var(--color-destructive)" } },
        (d > 0 ? "+" : "") + num(Math.round(d * 100) / 100) + (sufijo || "") + " frente a los anteriores"));
  }

  function Metricas() {
    const [webs] = usarDatos("/webs", 0);
    const [web, setWeb] = useState("");
    useEffect(() => { if (webs && webs.length && !web) setWeb(webs[0].slug); }, [webs]);
    const [r, setR] = useState(null);
    useEffect(() => { if (web) { setR(null); get("/metricas/" + web).then(setR).catch((e) => setR({ error: String(e.message || e) })); } }, [web]);
    if (!webs) return h("p", { style: tenue }, "Cargando…");
    return h("div", null,
      h("div", { style: { display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 } },
        webs.map((w) => h(Button, { key: w.slug, size: "sm", variant: w.slug === web ? "default" : "outline", onClick: () => setWeb(w.slug) }, w.nombre))),
      !r ? h("p", { style: tenue }, "Cargando…")
      : r.error ? h("p", { style: tenue }, r.error)
      : !r.hay_datos ? h("p", null, "Aún no hay datos de Search Console de esta web (se recogen cada día si está configurada).")
      : h("div", null,
          h("p", { style: tenue }, `Últimos ${r.dias} días hasta el ${r.hasta}, frente a los ${r.dias} anteriores (Search Console).` +
            (r.anterior.dias < r.dias ? ` Ojo: del periodo anterior solo hay ${r.anterior.dias} días de datos guardados; la comparación aún no es justa.` : "")),
          h("div", { style: { display: "flex", gap: 10, flexWrap: "wrap", marginBottom: 12 } },
            h(Dato, { nombre: "Clics", ahora: r.actual.clics, antes: r.anterior.clics }),
            h(Dato, { nombre: "Impresiones", ahora: r.actual.impresiones, antes: r.anterior.impresiones }),
            h(Dato, { nombre: "CTR", ahora: r.actual.ctr, antes: r.anterior.ctr, sufijo: " %" }),
            h(Dato, { nombre: "Posición media", ahora: r.actual.posicion, antes: r.anterior.posicion, inverso: true })),
          h("div", { style: caja }, h(Grafico, { serie: r.serie })),
          h("div", { style: caja }, h("strong", null, "De la página 2 a la 1: consultas en posiciones 8-20"),
            r.pagina_dos.length ? h("table", { style: { width: "100%", marginTop: 8, fontSize: 13, borderCollapse: "collapse" } },
              h("thead", null, h("tr", null, ["Consulta", "Página", "Impresiones", "Clics", "Posición"].map((t) => h("th", { key: t, style: { textAlign: "left", borderBottom: BORDE, padding: 4 } }, t)))),
              h("tbody", null, r.pagina_dos.map((f, i) => h("tr", { key: i },
                h("td", { style: { padding: 4 } }, f.consulta), h("td", { style: { padding: 4, wordBreak: "break-all" } }, f.pagina),
                h("td", { style: { padding: 4 } }, num(f.impresiones)), h("td", { style: { padding: 4 } }, num(f.clics)),
                h("td", { style: { padding: 4 } }, f.posicion)))))
            : h("p", { style: tenue }, "Ninguna en este periodo."))));
  }

  function Cambios() {
    const [webs] = usarDatos("/webs", 0);
    const [web, setWeb] = useState("");
    useEffect(() => { if (webs && webs.length && !web) setWeb(webs[0].slug); }, [webs]);
    const [cs, setCs] = useState(null);
    useEffect(() => { if (web) get("/cambios/" + web).then(setCs).catch(() => setCs([])); }, [web]);
    if (!webs) return h("p", { style: tenue }, "Cargando…");
    return h("div", null,
      h("div", { style: { display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 } },
        webs.map((w) => h(Button, { key: w.slug, size: "sm", variant: w.slug === web ? "default" : "outline", onClick: () => setWeb(w.slug) }, w.nombre))),
      !cs ? h("p", { style: tenue }, "Cargando…") : !cs.length ? h("p", null, "Aún no se ha publicado nada desde hermes-seo.")
      : cs.map((c) => h("div", { key: c.id, style: caja },
          h("div", null, h("strong", null, (c.ts || "").slice(0, 10) + " · " + (c.clase || "cambio")), " ", c.url ? h("a", { href: c.url, target: "_blank", rel: "noreferrer" }, c.url) : null),
          h("div", { style: { marginTop: 4 } }, "Hipótesis: " + (c.hipotesis || "—")),
          h("div", { style: tenue }, (c.resultado || "") + " · aprobado por " + (c.firma || "—")),
          h("div", { style: tenue }, "Veredicto: a los 28 días, pídeselo a su encargado («¿qué tal fue el cambio del " + (c.ts || "").slice(0, 10) + "?»)."))));
  }

  const SECCIONES = [["Cartera", Cartera], ["Decisiones", Decisiones], ["Métricas", Metricas], ["Cambios", Cambios]];

  function Pagina() {
    const [sec, setSec] = useState(0);
    return h("div", { style: { padding: 16, maxWidth: 960 } },
      h("h1", { style: { fontSize: 20, fontWeight: 600, marginBottom: 4 } }, "SEO"),
      h("p", { style: { ...tenue, marginBottom: 12 } }, "Tus webs, lo que espera tu decisión, sus datos y lo que se ha cambiado. Para pedir trabajo, habla con la coordinadora o con el encargado de cada web."),
      h("div", { style: { display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" } },
        SECCIONES.map(([n], i) => h(Button, { key: n, size: "sm", variant: i === sec ? "default" : "ghost", onClick: () => setSec(i) }, n))),
      h(SECCIONES[sec][1]));
  }
  Pagina.partes = { Cartera, Decisiones, Metricas, Cambios };
  window.__HERMES_PLUGINS__.register("hermes-seo", Pagina);
})();
