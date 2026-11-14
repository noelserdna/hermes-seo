---
name: investigacion-a-fondo
description: "Primera etapa de una pieza: investiga el tema con fuentes primarias, compara con los 5 primeros resultados y deja la nota de fuentes."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Investigacion a fondo

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
1. Lee el brief y lo que la web ya tiene sobre el tema (mapa temático, páginas relacionadas): no repitas, enlaza.
2. Investiga con fuentes primarias. Para cada afirmación que vaya a sostener el texto: URL, fecha, paráfrasis breve y
   si es hecho, propuesta u opinión. Si hay código o pasos, que sean literales de la fuente o probados.
3. **Lo que ya ranquea**: busca la búsqueda principal como el público y abre los 5 primeros resultados ajenos; anota
   secciones, ejemplos, datos y fecha. Tabla de huecos: | Tema o sección | La web | R1…R5 | Prioridad |.
4. **Preguntas reales** del público sobre el tema, como las escribe la gente, con enlace: serán los apartados.
5. Qué tendrá esta página que no tenga ninguna de las cinco. Si no hay nada, dilo en la primera línea: es motivo para
   no escribirla (la puerta lo decidirá).
6. Escribe `investigacion.md`: búsqueda principal y secundarias, fuentes (tabla), huecos, preguntas, ángulo, enlaces
   internos posibles y conceptos que el lector necesita antes.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
