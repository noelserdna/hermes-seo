---
name: mapa-tematico
description: "Mapa temático (una búsqueda, una página) y plan editorial con demanda medida y sin canibalización."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Mapa tematico

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
1. Con `mercado.md` (y `competencia.md` si existe) y las páginas que ya tiene la web (sitemap, Search Console):
   asigna cada tema a **una sola página** (existente o nueva). Si dos páginas compiten por lo mismo, márcalo
   (canibalización) y propone cuál se queda y qué pasa con la otra.
2. Plan editorial: **como mucho 8 piezas** (nuevas o actualizaciones), ordenadas por clics potenciales y por facilidad
   (¿la web tiene ya autoridad en ese tema?). Cada una con: búsqueda principal, demanda medida, intención, página
   destino (nueva o URL), por qué ahora, y el ángulo que la diferencia.
3. Respeta las políticas del cliente (si hay congelación de piezas nuevas, el plan son actualizaciones).
4. Escribe `plan-editorial.md`: el mapa temático (tabla tema → página) y el plan. La persona lo aprueba en la puerta;
   después, el encargado lo pasa a la wiki.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
