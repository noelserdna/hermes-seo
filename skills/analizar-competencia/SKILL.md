---
name: analizar-competencia
description: "Competencia en búsqueda: qué cubren los competidores, qué publican y dónde están sus huecos."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Analizar competencia

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-investigador`).

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
1. Competidores: los de `contexto-cliente.md`. Ejecuta `sitemaps-competencia --cliente <nombre corto>` para ver qué
   publican (y qué es nuevo).
2. Para los temas de `mercado.md` con más demanda, busca como lo haría el público y anota los 5 primeros resultados:
   quién sale, qué formato (guía, lista, comparativa, herramienta), fecha, qué cubren.
3. Tabla de huecos por tema: | Tema | La web | Competidor 1…5 | Hueco |. «Nadie lo cubre bien» es un ángulo propio.
4. Escribe `competencia.md`: lo que hacen bien (para no competir de frente sin ventaja), los huecos y las amenazas.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
