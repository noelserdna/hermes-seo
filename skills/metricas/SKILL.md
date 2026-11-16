---
name: metricas
description: "Métricas de la semana en números absolutos (Search Console, Bing, analítica, bots de IA) y como mucho 3 propuestas."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Metricas

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
1. Datos de Search Console (si hay `gsc`): **las cifras salen de `datos-resumen.json`** (en la carpeta del encargo; lo
   deja el código): 28 días frente a los 28 anteriores, páginas, países, dispositivos, consultas de marca, consultas en
   posiciones 8-20 y `bajo_ctr` (páginas con muchas impresiones y pocos clics para su posición). No calcules ni copies
   cifras de otro sitio, y antes de escribir «no hay datos de X» mira su clave en ese fichero. Con el MCP `seo` puedes
   profundizar en algo concreto, citando de dónde sale.
2. Bing (si hay `bing`), analítica (si hay `analitica`) y bots de IA (`bots-ia`, si la analítica es Cloudflare).
3. Los cambios publicados en las últimas semanas (`cambios.jsonl` del cliente): ¿se ve algo? Sin veredictos: los da
   la pipeline `veredicto` a los 28 días.
4. Escribe `metricas.md`: números absolutos primero (tabla corta), lo que se mueve, **como mucho 3 propuestas**
   (cada una: qué, por qué con el dato, hipótesis, pipeline que la haría) y «Lo que no sabemos».

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
