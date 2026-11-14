---
name: preparar-publicacion
description: "Deja la pieza lista para publicar (aplicando las revisiones) y describe exactamente qué se publicaría, sin publicarlo."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Preparar publicacion

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
1. Aplica al borrador los cambios obligatorios de `verificacion.md` y `lectura.md`. Si alguno de los dos dijo CAMBIOS
   y no puedes resolverlo, escríbelo arriba de todo: la puerta lo enseñará.
2. Deja la versión final en `borrador.md` (sobrescribe) con su bloque inicial al día.
3. Escribe `publicacion.json`:
   ```json
   {"tipo": "nuevo | actualizacion", "titulo": "…", "meta_descripcion": "…", "url": "https://…",
    "contenido": "borrador.md", "busqueda_principal": "…",
    "clase": "articulo | actualizacion", "hipotesis": "Qué esperamos que cambie y en cuánto tiempo (medible)",
    "enlaces_internos": ["https://…"], "verificacion": "APROBADO | CAMBIOS", "lectura": "APROBADO | CAMBIOS"}
   ```
   El adaptador de publicación de la web lo convertirá en un PR, un borrador de WordPress o un paquete para quien la
   lleve. Tú no publicas nada.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
