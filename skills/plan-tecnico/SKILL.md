---
name: plan-tecnico
description: "Convierte la auditoría técnica en un plan de cambios pequeño, ordenado y medible."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Plan tecnico

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-analista`).

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
1. Lee `auditoria.md`. Para cada problema decide: arreglarlo, vigilarlo o ignorarlo (y por qué).
2. Plan de **como mucho 7 cambios**, en orden: primero lo que bloquea el tráfico. Cada uno con:
   qué se cambia (URL o patrón), por qué (el hallazgo), cómo se comprueba que quedó bien, riesgo (¿toca páginas con
   tráfico, redirecciones, borra algo?) y si se puede deshacer.
3. Si la web publica sin acceso al código (adaptador `entrega`), escribe cada cambio de forma que lo aplique otra
   persona sin saber SEO.
4. Escribe `plan-tecnico.md`: el plan, lo que se deja para más adelante y «Lo que no sabemos».

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
