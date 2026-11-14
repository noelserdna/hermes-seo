---
name: verificar
description: "Verificación de hechos frase a frase contra sus fuentes; veredicto APROBADO o CAMBIOS."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Verificar

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-verificador`).

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
1. Lee el borrador (o el cambio) y la nota de fuentes. Sin el contexto del encargo: con desconfianza.
2. Cada afirmación de hechos: abre la fuente y comprueba que dice eso (no más). Vigila el alcance («puede» ≠ «debe»,
   propuesta ≠ estándar), cifras, fechas, nombres, enlaces (que respondan y lleven a lo que dicen) y código o pasos.
3. Si es un cambio técnico, comprueba que hace lo que dice el análisis y que no rompe nada evidente (redirecciones en
   bucle, canonical a otra página, páginas con tráfico que desaparecen).
4. Escribe `verificacion.md`: tabla | Afirmación | Fuente | ¿Correcto? | Cambio |, la lista de cambios obligatorios y
   en la última línea `VEREDICTO: APROBADO` o `VEREDICTO: CAMBIOS`. Nunca «aprobado con reservas».

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
