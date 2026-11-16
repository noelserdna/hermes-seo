---
name: revision-mensual
description: "Revisión mensual: auditoría, enlaces, indexación y visibilidad; como mucho 3 encargos."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Revision mensual

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-analista`).

## Antes de empezar (siempre)
- Estás en la carpeta del encargo. Lee `brief.md` (qué se pidió), `contexto-cliente.md` (la web: público, voz, mercados,
  capacidades, nombre corto para las herramientas) y las salidas de las etapas anteriores que te indique el encargo.
- La memoria de la web es su wiki (ruta en `contexto-cliente.md`): mira `index.md` y las páginas que toquen (sobre todo
  el mapa temático) antes de proponer nada. Léela; no la edites desde una etapa.
- Herramientas de datos: en la carpeta que indica `contexto-cliente.md`, siempre con `--cliente <nombre corto>`
  (`--help` para su uso). Si falta una clave, la herramienta lo dice: anótalo en tu salida y sigue con lo demás.
- Escribe tu resultado en el fichero que te pide el encargo: lo que se va a publicar, en el idioma de la web; los
  informes, en el «idioma de los informes» de `contexto-cliente.md`. Nada de publicar, desplegar,
  escribir a nadie ni tocar la configuración: eso es de una puerta.

## Procedimiento
1. Lee `auditoria.md` (etapa anterior) y compáralo con la del mes pasado (informes del cliente): qué se arregló, qué
   apareció.
2. Enlaces entrantes (`enlaces-bing --cliente <nombre corto>`, si hay `bing`) y su evolución.
3. Indexación: páginas del sitemap no indexadas (MCP `seo`, `inspeccionar_url` sobre una muestra).
4. Escribe `revision.md`: estado en 10 líneas, **como mucho 3 encargos** priorizados (con la pipeline que los haría
   y su hipótesis) y «Lo que no sabemos».

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
