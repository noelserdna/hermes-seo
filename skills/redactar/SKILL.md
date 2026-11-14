---
name: redactar
description: "Escribe la pieza (nueva o actualización) a partir de la investigación, con la voz de la web, y deja el borrador."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Redactar

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-redactor`).

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
1. Lee `investigacion.md`, el brief, la voz y el público de `contexto-cliente.md` y, si es una actualización, la
   página actual (descárgala). Si hay `feedback` de una ronda anterior en el encargo, aplícalo primero.
2. Estructura: título de 40 a 60 caracteres con la búsqueda principal; la respuesta en las dos primeras frases;
   apartados que respondan las preguntas reales (cada uno empieza respondiendo); un ejemplo concreto que haga de hilo;
   cierre con el siguiente paso lógico para el lector (y el objetivo de la web, si encaja).
3. Solo afirmas lo que está en la investigación, con su enlace cuando aporte. Nada de cifras, testimonios ni fechas
   inventadas. Nada de relleno ni fórmulas de máquina (tríadas, moralejas, «en el mundo actual»…).
4. Enlaces internos a páginas que existen (compruébalas) y ninguno a páginas que compitan por la misma búsqueda.
5. Escribe `borrador.md` con un bloque inicial:
   ```
   ---
   titulo: …
   meta_descripcion: … (140-160 caracteres)
   busqueda_principal: …
   url: … (propuesta o la existente)
   ---
   ```
   y debajo el texto en Markdown.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
