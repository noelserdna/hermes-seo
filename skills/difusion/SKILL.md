---
name: difusion
description: "Busca dónde mover lo publicado (comunidades, listas, plataformas) con el texto listo; cada destino se aprueba aparte."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Difusion

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
1. Piezas recientes de la web que merezcan difusión (las publicadas en el último mes, o la que diga el brief).
2. **5 destinos como mucho**: dónde está el público (comunidades, listas curadas, plataformas con canonical) y sus
   normas (autopromoción, formato). Descarta los que lo prohíben.
3. Para cada destino: por qué encaja, qué se publicaría (texto listo, honesto, sin exagerar) y quién lo publica
   (siempre una persona o, si el cliente lo tiene configurado, el sistema tras su aprobación).
4. Escribe `difusion.md`. No publicas nada.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
