---
name: revision-lectura
description: "Revisión como la haría el lector que llega desde un buscador: claridad, jerga, saltos, frases de máquina, respuesta arriba."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Revision lectura

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-editor`).

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
1. Lee el borrador como alguien del público de la web que llega por primera vez desde un buscador o una IA.
2. Marca, con la línea: términos sin explicar, saltos lógicos, pasos que se dan por sabidos, frases que suenan a
   máquina, párrafos que no aportan, apartados que no empiezan respondiendo, título o descripción que prometen otra
   cosa.
3. Comprueba la estructura SEO legible: respuesta en las dos primeras frases, un H1, apartados que responden
   preguntas reales, enlaces internos con texto descriptivo.
4. Escribe `lectura.md`: cambios concretos línea a línea (antes → después) y en la última línea
   `VEREDICTO: APROBADO` o `VEREDICTO: CAMBIOS`.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
