---
name: comprobar-cambios
description: "Comprobación final: los cambios obligatorios de la verificación están aplicados en todas las versiones."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Comprobar cambios

Etapa de una pipeline de hermes-seo (perfil habitual: `seo-verificador`). Va después de «preparar»: no vuelve a
verificar el texto entero, solo que lo que la verificación pidió está hecho, en la pieza principal y en cada traducción.

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
1. Lee `verificacion.md`: su lista de **cambios obligatorios**. Si su veredicto es APROBADO y no hay cambios
   obligatorios, escribe `comprobacion.md` diciéndolo y termina con `VEREDICTO: APROBADO`.
2. Lee `publicacion.json`: el contenido (`contenido`) y cada traducción (`traducciones[].contenido`). Esas son las
   versiones que se van a publicar; ninguna puede quedarse fuera.
3. Para cada cambio obligatorio y cada versión: ¿está aplicado? Busca la frase que había que quitar o cambiar (y sus
   equivalentes en el otro idioma) y comprueba que lo nuevo dice lo que pidió la verificación, ni más ni menos.
4. Tú no corriges el texto: solo compruebas. Escribe `comprobacion.md` con una tabla | Cambio | Versión | ¿Aplicado? |
   Dónde |, y en la última línea `VEREDICTO: APROBADO` (todo aplicado en todas las versiones) o `VEREDICTO: CAMBIOS`
   (con la lista exacta de lo que falta y en qué versión).

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
