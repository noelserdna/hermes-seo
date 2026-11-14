---
name: veredicto
description: "Compara los datos antes y después de un cambio publicado (28 días) y propone mantener, revertir o insistir."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Veredicto

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
1. Busca el cambio en `cambios.jsonl` del cliente (id del brief): fecha, URL, clase e hipótesis.
2. Datos de las URL afectadas: 28 días antes frente a 28 días después (si aún no han pasado 28 días, dilo y para).
   Clics, impresiones, CTR, posición; y el conjunto de la web para descontar la tendencia general.
3. ¿Se cumple la hipótesis? Con cuidado: pocas impresiones no permiten concluir; estacionalidad; otros cambios a la
   vez. Di cuánta confianza hay.
4. Escribe `veredicto.md`: la tabla antes/después, la lectura honesta y la propuesta (mantener, revertir, insistir
   con otra cosa). Decide la persona en la puerta.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
