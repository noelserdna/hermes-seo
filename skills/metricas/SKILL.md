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
- Escribe tu resultado en el fichero que te pide el encargo, en el idioma de la web. Nada de publicar, desplegar,
  escribir a nadie ni tocar la configuración: eso es de una puerta.

## Procedimiento
1. Datos de Search Console (si hay `gsc`): `hseo datos resumen <nombre corto>` da los últimos 28 días frente a los
   28 anteriores y las consultas en posiciones 8-20 («de la página 2 a la 1»), desde la copia diaria. Con el MCP
   `seo` puedes profundizar (consultas y páginas que más suben y bajan).
2. Bing (si hay `bing`), analítica (si hay `analitica`) y bots de IA (`bots-ia`, si la analítica es Cloudflare).
3. Los cambios publicados en las últimas semanas (`cambios.jsonl` del cliente): ¿se ve algo? Sin veredictos: los da
   la pipeline `veredicto` a los 28 días.
4. Escribe `metricas.md`: números absolutos primero (tabla corta), lo que se mueve, **como mucho 3 propuestas**
   (cada una: qué, por qué con el dato, hipótesis, pipeline que la haría) y «Lo que no sabemos».

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
