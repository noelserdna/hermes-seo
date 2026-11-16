---
name: alta-comprobar
description: "Alta de una web: comprueba qué hay (sitemap, robots, Search Console, Bing, analítica, IndexNow, datos estructurados) y deja la lista de lo que falta para que una persona lo complete."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Alta comprobar

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
1. Con el dominio de `contexto-cliente.md`, comprueba en la web (lectura, `curl -sI` / `curl -s`):
   - responde 200 en https, redirige http→https y www↔sin www a una sola versión;
   - `robots.txt`: existe, no bloquea lo que debe indexarse, declara el sitemap;
   - sitemap: existe, es válido, cuántas URL y si responden 200;
   - `<title>`, meta descripción, canonical y `<html lang>` de la portada y de 3 páginas del sitemap;
   - datos estructurados (JSON-LD) presentes o no; `llms.txt` presente o no; IndexNow (clave en la raíz) o no.
2. Capacidades configuradas (están en `contexto-cliente.md`): Search Console, Bing, analítica, publicación. Para cada
   una que falte, explica **qué tiene que hacer la persona** (paso a paso, sin claves en el chat: dónde ponerlas) y
   qué se pierde mientras falte.
3. Si la web es **nueva** (sin contenido), sustituye el punto 1 por: qué hay que tener antes de publicar (dominio,
   https, sitemap automático, robots, analítica, alta en Search Console y Bing) según cómo se va a construir.
4. Escribe `alta.md`:
   - **Lo que ya está bien** (lista corta);
   - **Lo que falta y quién lo hace** (tabla: qué · por qué importa · quién · cómo), primero lo que bloquea medir;
   - **Lo que propones configurar en hermes-seo** (público, voz, mercados, competidores si los ves claros) para que la
     coordinadora lo proponga;
   - **Lo que no sabemos**.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
