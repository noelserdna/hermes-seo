---
name: analizar-cambio
description: "Analiza un cambio SEO técnico pedido: qué hay hoy, qué cambiar, riesgo e hipótesis medible."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Analizar cambio

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
1. Lee qué se pide en el brief. Mira el estado actual en la web (lectura) y, si hay Search Console, el rendimiento de
   las URL afectadas (90 días).
2. Propón el cambio exacto (URL o patrón, antes → después), el riesgo (¿toca páginas con tráfico?, ¿redirige o
   elimina algo?), cómo deshacerlo y la **hipótesis medible** (qué métrica, cuánto, en cuántos días).
3. Si el cambio no tiene sentido o es arriesgado sin evidencia, dilo en la primera línea.
4. Escribe `analisis.md`.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
