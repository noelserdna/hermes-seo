---
name: auditoria-inicial
description: "Auditoría técnica de una web desde su sitemap: estados, redirecciones, canonical, noindex, títulos, metas, H1, alt, enlaces rotos y huérfanas."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Auditoria inicial

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
1. Ejecuta `auditoria-web --cliente <nombre corto>` (guarda su salida en el encargo). Si hay Search Console
   (capacidad `gsc`), usa el MCP `seo` (`estado_sitemaps`, `inspeccionar_url` para 5 URL clave) para la indexación.
2. Agrupa los hallazgos por gravedad:
   - **bloquea el tráfico** (5xx, noindex por error, canonical a otra página, robots que bloquea, redirecciones en
     cadena, páginas del sitemap que no responden 200);
   - **resta** (títulos > 60 o duplicados, sin meta, H1 ausente o repetido, enlaces rotos, huérfanas);
   - **mejora** (alt, datos estructurados, rendimiento evidente).
3. Para cada grupo, cuántas URL y 3 ejemplos con su URL. Nada de listas de cientos de líneas: la salida completa queda
   como fichero aparte en el encargo.
4. Escribe `auditoria.md` con ese resumen, la fecha y lo que no se pudo comprobar.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
