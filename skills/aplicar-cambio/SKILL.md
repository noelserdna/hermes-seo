---
name: aplicar-cambio
description: "Prepara el cambio SEO técnico tal como se aplicaría (sin aplicarlo) y lo describe en publicacion.json."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Aplicar cambio

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-redactor`).

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
1. Con `analisis.md`, prepara exactamente lo que cambiaría (texto nuevo de títulos o metas, reglas de redirección,
   enlaces, datos estructurados), sin aplicarlo en la web.
2. Escribe `publicacion.json`:
   ```json
   {"tipo": "cambio-tecnico", "cambios": [{"accion": "meta | titulo | redireccion | enlace | datos-estructurados | otro",
     "url": "https://…", "antes": "…", "despues": "…"}],
    "clase": "tecnico", "hipotesis": "…", "como_deshacer": "…"}
   ```

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
