---
name: visibilidad-ia
description: "Visibilidad en IA: preguntas de decisión a ChatGPT, Claude y Brave; si citan o mencionan la web y por qué no."
version: 0.1.0
metadata:
  hermes:
    tags: [SEO, hermes-seo]
    category: hermes-seo
---

# Visibilidad ia

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
1. Preguntas: `preguntas-decision.md` en la carpeta de la web (una por línea; es lo que leen las herramientas). Si no
   existe, propón 10 preguntas de decisión de su público y anótalas en el informe para que la coordinadora las guarde.
2. Motores: si `contexto-cliente.md` dice «Motores para la visibilidad en IA», usa **solo esos** (los demás no se
   lanzan: tienen coste o no se quieren). Si no lo dice, los tres. ChatGPT con búsqueda: `chatgpt-busca --cliente <nombre corto>` (coste de API: ya aprobado al lanzar). Brave:
   `brave-busca --cliente <nombre corto>`. Claude con búsqueda web: `claude-busca --cliente <nombre corto>` (tarda;
   lánzalo con un timeout de terminal amplio).
   Si `contexto-cliente.md` dice «Modelos para la visibilidad en IA», lanza ese motor una vez con cada modelo
   (`--modelo <id>`; cada uno guarda su fichero). El primero es el principal; los otros sirven para ver lo que ve quien
   usa la versión gratuita o un modelo pequeño.
3. Por pregunta y motor: ¿cita la web (enlace)?, ¿la menciona?, ¿a quién cita en su lugar? Separa cita y mención.
4. Tabla de huecos: por qué citan a otros (formato, autoridad, frescura, la web no tiene esa página…). Antes de decir
   que la web no tiene una página, mira su sitemap (todas sus URL, en todos sus idiomas): no lo supongas.
5. Las cifras: `hseo ia resumen <nombre corto>` (sin modelo): por motor, respuestas, cita (enlace) y mención, con su
   intervalo, competidores y si algo cambió frente a la ronda anterior (solo «sube/baja» si los intervalos no se
   solapan). Usa esas cifras tal cual; tu trabajo es explicar los huecos, no contar.
6. Escribe `visibilidad.md`: resultado por motor (x de N) y, si hubo varios modelos, la comparación que da el resumen
   (`modelos`: más citas, menos o sin diferencia que se pueda afirmar) y en qué preguntas cambia; la tabla de huecos, **como mucho 3 acciones** y «Lo que no
   sabemos». Si una herramienta falló o faltan filas, dilo: un informe incompleto no se presenta como completo.

## Al terminar
Termina tu respuesta con una sola línea que resuma el resultado (la estación la usa como resumen de la tarjeta).
