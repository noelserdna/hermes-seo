---
name: investigar-mercado
description: "Mercado y demanda de búsqueda de una web: qué busca su público, con qué palabras y cuánto, en sus mercados."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Investigar mercado

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-investigador`).

## Antes de empezar (siempre)
- Estás en la carpeta del encargo. Lee `brief.md` (qué se pidió), `contexto-cliente.md` (la web: público, voz, mercados,
  capacidades, nombre corto para las herramientas) y las salidas de las etapas anteriores que te indique el encargo.
- La memoria de la web es su wiki (ruta en `contexto-cliente.md`): mira `index.md` y las páginas que toquen (sobre todo
  el mapa temático) antes de proponer nada. Léela; no la edites desde una etapa.
- Herramientas de datos: en la carpeta que indica `contexto-cliente.md`, siempre con `--cliente <nombre corto>`
  (`--help` para su uso). Si falta una clave, la herramienta lo dice: anótalo en tu salida y sigue con lo demás.
- Escribe tu resultado en el fichero que te pide el encargo, en el idioma de la web. Nada de publicar, desplegar,
  escribir a nadie ni tocar la configuración: eso es de una puerta.

## Procedimiento
1. A partir del negocio y el público (`contexto-cliente.md`) y de lo que ya tiene la web, haz una lista de 15-30
   búsquedas semilla: lo que haría su público para encontrarla («qué es…», «cómo…», «mejor…», «… precio», «… vs …»).
2. Mide la demanda con `demanda-bing --cliente <nombre corto> "<consulta>" …` (impresiones por mercado). Si hay
   Search Console, cruza con las consultas por las que la web ya aparece (MCP `seo`, `rendimiento_busqueda`, 90 días).
3. Agrupa en temas por intención (informativa, comparativa, transaccional, navegacional). Por tema: búsquedas,
   demanda, si la web ya tiene página y cómo rinde.
4. Preguntas reales del público (foros, Reddit, Hacker News, «otras preguntas» del buscador), tal como las escribe la
   gente, con enlace.
5. Escribe `mercado.md`: la tabla de temas con demanda medida (fuente y fecha), las preguntas reales y «Lo que no
   sabemos». Nada de cifras de demanda inventadas: lo que no se pudo medir, se dice.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
