---
name: radar
description: "Radar periódico del nicho de una web: qué se mueve, qué busca la gente y qué ha publicado la competencia; propone como mucho 3 piezas con demanda medida."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Radar

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
1. Qué ha pasado en el nicho desde el último radar (fuentes primarias del sector, novedades, cambios): con URL y fecha.
2. Qué han publicado los competidores (`sitemaps-competencia --cliente <nombre corto>`).
3. Qué pregunta la gente (foros, Reddit, Hacker News, preguntas del buscador).
4. Si hay apuntes pendientes en la wiki o en `briefs/` del cliente, revísalos.
5. Para cada idea candidata: ¿la web ya lo tiene? (mapa temático), ¿hay demanda? (`demanda-bing`), ¿alguien lo cubre
   bien? Descarta lo que no tenga demanda ni ángulo.
6. Escribe `radar.md`: novedades (5 líneas como mucho), **como mucho 3 propuestas** (búsqueda, demanda, página
   nueva o actualización, ángulo, prioridad) y lo descartado en una línea cada uno. Un día flojo se dice: cero
   propuestas es una respuesta válida.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
