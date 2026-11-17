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
        w.pausada ? h(Badge, { variant: "destructive" }, "en pausa") : null,
        w.puertas ? h(Badge, null, "🚪 " + w.puertas) : null),
      h("div", { style: { ...tenue, marginTop: 6 } }, "Puede: " + (w.capacidades.join(", ") || "nada configurado aún")),
      w.encargos.length
        ? h("ul", { style: { margin: "8px 0 0 18px" } }, w.encargos.map((e) => h("li", { key: e.id }, e.nombre + " · " + e.estado)))
        : h("div", { style: { ...tenue, marginTop: 6 } }, "Nada en marcha."))));
  }

  function Puerta({ p }) {
    // Solo lectura: las puertas se deciden en Telegram o por correo (el panel no decide).
    return h("div", { style: caja },
      h("strong", null, p.titulo),
      h("pre", { style: { whiteSpace: "pre-wrap", fontFamily: "inherit", margin: "8px 0", maxHeight: 320, overflow: "auto" } }, p.texto),
      p.estado === "abierta" ? h("p", { style: tenue }, "Se decide en Telegram o por correo.")
      : p.estado === "decidida" ? h("span", null, "🕒 Decidido por " + p.decidio + ": «" + p.decision.verbo + "». Se ejecuta al acabar la ventana.")
      : h("p", { style: { color: "var(--color-destructive)" } }, "⚠️ " + (p.error || p.estado)));
  }

  function Decisiones() {
    const [ps, error, recargar] = usarDatos("/puertas", 10000);
    if (error) return h("p", { style: tenue }, error);
    if (!ps) return h("p", { style: tenue }, "Cargando…");
    if (!ps.length) return h("p", null, "No hay nada pendiente de decidir.");
    return h("div", null, ps.map((p) => h(Puerta, { key: p.id, p })));
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

  function Tabla({ datos }) {
    return h("table", { style: { width: "100%", fontSize: 13, borderCollapse: "collapse" } }, h("tbody", null,
      Object.entries(datos).map(([k, v]) => h("tr", { key: k },
        h("td", { style: { padding: "3px 8px 3px 0", ...tenue, width: "38%", verticalAlign: "top" } }, k),
        h("td", { style: { padding: 3, wordBreak: "break-word" } }, v == null || v === "" ? "—" : String(v))))));
  }

  function Campo({ slug, c, alGuardar }) {
    const aTexto = (v) => (v == null ? "" : Array.isArray(v) ? v.join("\n") : String(v));
    const [editando, setEditando] = useState(false);
    const [v, setV] = useState(aTexto(c.valor));
    const [msg, setMsg] = useState("");
    useEffect(() => { setV(aTexto(c.valor)); }, [c.valor]);
    const guardar = (valor) => post("/config/" + slug, { clave: c.clave, valor })
      .then(() => { setMsg("✅ Guardado"); setEditando(false); alGuardar(); })
      .catch((e) => setMsg("⚠️ " + String(e.message || e)));
    const mostrar = c.tipo === "si-no" ? (c.valor ? "sí" : "no") : aTexto(c.valor) || "—";
    return h("div", { style: { padding: "8px 0", borderBottom: BORDE } },
      h("div", { style: { display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" } },
        h("strong", { style: { fontSize: 14 } }, c.etiqueta),
        c.tipo === "si-no"
          ? h(Button, { size: "sm", variant: "outline", onClick: () => guardar(!c.valor) }, c.valor ? "Quitar" : "Activar")
          : !editando ? h(Button, { size: "sm", variant: "ghost", onClick: () => { setEditando(true); setMsg(""); } }, "Cambiar") : null),
      c.ayuda ? h("div", { style: tenue }, c.ayuda) : null,
      editando
        ? h("div", { style: { marginTop: 6 } },
            c.tipo === "texto" || c.tipo === "lista"
              ? h("textarea", { value: v, onChange: (e) => setV(e.target.value), rows: c.tipo === "lista" ? 4 : 5,
                  style: { width: "100%", fontFamily: "inherit", fontSize: 13, padding: 6, border: BORDE, borderRadius: 6, background: "transparent", color: "inherit" } })
              : h(Input, { value: v, onChange: (e) => setV(e.target.value), type: c.tipo === "numero" ? "number" : "text", placeholder: c.tipo === "fecha" ? "AAAA-MM-DD" : "" }),
            h("div", { style: { display: "flex", gap: 6, marginTop: 6 } },
              h(Button, { size: "sm", onClick: () => guardar(v) }, "Guardar"),
              h(Button, { size: "sm", variant: "ghost", onClick: () => { setEditando(false); setV(aTexto(c.valor)); setMsg(""); } }, "Cancelar")))
        : h("div", { style: { whiteSpace: "pre-wrap", marginTop: 4, fontSize: 13 } }, mostrar),
      msg ? h("div", { style: { fontSize: 12, marginTop: 4 } }, msg) : null);
  }

  function Configuracion() {
    const [webs] = usarDatos("/webs", 0);
    const [web, setWeb] = useState("");
    useEffect(() => { if (webs && webs.length && !web) setWeb(webs[0].slug); }, [webs]);
    const [cfg, setCfg] = useState(null);
    const cargar = useCallback(() => { if (web) get("/config/" + web).then(setCfg).catch((e) => setCfg({ error: String(e.message || e) })); }, [web]);
    useEffect(() => { setCfg(null); cargar(); }, [cargar]);
    if (!webs) return h("p", { style: tenue }, "Cargando…");
    const seccion = (t, ...hijos) => h("div", { style: caja }, h("strong", null, t), h("div", { style: { marginTop: 8 } }, ...hijos));
    return h("div", null,
      h("div", { style: { display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 12 } },
        webs.map((w) => h(Button, { key: w.slug, size: "sm", variant: w.slug === web ? "default" : "outline", onClick: () => setWeb(w.slug) }, w.nombre))),
      !cfg ? h("p", { style: tenue }, "Cargando…") : cfg.error ? h("p", { style: tenue }, cfg.error) : h("div", null,
        cfg.alta && !cfg.alta.completo ? h("p", null, "🛬 Alta en curso: " + cfg.alta.hechos + " de 10 pasos.") : null,
        seccion("La web", h(Tabla, { datos: cfg.web })),
        seccion("Lo que puedes cambiar", h("p", { style: tenue }, "Se aplica en el siguiente trabajo, sin reiniciar nada. Cada cambio queda en el historial."),
          cfg.editables.map((c) => h(Campo, { key: c.clave, slug: web, c, alGuardar: cargar }))),
        seccion("Cómo publica", h(Tabla, { datos: cfg.publicacion }), h("p", { style: { ...tenue, marginTop: 6 } }, "Esto, el contacto y las claves se cambian con la coordinadora: las claves nunca pasan por aquí.")),
        seccion("Contacto", h(Tabla, { datos: cfg.contacto })),
        seccion("Cómo trabaja (igual en todas las webs salvo «preparar»)", cfg.como_trabaja.map((p) => h("div", { key: p.id, style: { marginBottom: 10 } },
          h("div", null, h("strong", { style: { fontSize: 13 } }, p.nombre), " ",
            p.propia ? h(Badge, { variant: "outline" }, p.hereda ? "adaptada" : "propia de esta web") : null,
            p.puerta ? h("span", { style: tenue }, " → 🚪 " + p.puerta) : null),
          h("div", { style: { ...tenue, marginTop: 2 } }, p.etapas.map((e) => e.id + " (" + e.ejecutor + (e.modelo && e.modelo !== "el del perfil" ? ", " + e.modelo : "") + ")").join(" → "))))),
        seccion("Tareas programadas", h(Tabla, { datos: Object.fromEntries(cfg.tareas.map((t) => [t.nombre, t.horario])) })),
        seccion("Puede", h("div", { style: tenue }, cfg.capacidades.join(", ") || "nada configurado aún")),
        seccion("Historial de cambios", !cfg.historial.length ? h("p", { style: tenue }, "Sin cambios registrados.") :
          cfg.historial.map((r, i) => h("div", { key: i, style: { fontSize: 12, padding: "4px 0", borderBottom: BORDE } },
            h("div", null, (r.ts || "").slice(0, 16).replace("T", " ") + " · " + (r.quien || "—") + " · ", h("strong", null, r.clave)),
            h("div", { style: tenue }, r.antes + " → " + r.despues))))));
  }

  const SECCIONES = [["Cartera", Cartera], ["Decisiones", Decisiones], ["Métricas", Metricas], ["Cambios", Cambios], ["Configuración", Configuracion]];

  function Pagina() {
    const [sec, setSec] = useState(0);
    return h("div", { style: { padding: 16, maxWidth: 960 } },
      h("h1", { style: { fontSize: 20, fontWeight: 600, marginBottom: 4 } }, "SEO"),
      h("p", { style: { ...tenue, marginBottom: 12 } }, "Tus webs, lo que espera tu decisión, sus datos, lo que se ha cambiado y su configuración. Para pedir trabajo, habla con la coordinadora o con el encargado de cada web."),
      h("div", { style: { display: "flex", gap: 6, marginBottom: 16, flexWrap: "wrap" } },
        SECCIONES.map(([n], i) => h(Button, { key: n, size: "sm", variant: i === sec ? "default" : "ghost", onClick: () => setSec(i) }, n))),
      h(SECCIONES[sec][1]));
  }
  Pagina.partes = { Cartera, Decisiones, Metricas, Cambios, Configuracion };
  window.__HERMES_PLUGINS__.register("hermes-seo", Pagina);
})();
