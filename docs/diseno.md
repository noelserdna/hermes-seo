# Diseño de hermes-seo

Plugin agnóstico de SEO para Hermes Agent: cada web es un **cliente**, con su encargado, su memoria y su tablero, y
todo el ciclo de vida (alta → base técnica → estrategia → producción → publicación → difusión → telemetría → decisión
→ mantenimiento) se recorre con pipelines declarativas y puertas.

Parte del esqueleto de [hermes-sdd](https://github.com/noelserdna/hermes-sdd), copiado y adaptado (prefijo `hseo_`),
sin depender de él en ejecución.

> **Formato:** la configuración del cliente y las pipelines son **JSON** (no YAML), como en hermes-sdd: se leen con
> `jq` desde bash y con la biblioteca estándar desde Python, sin depender de PyYAML (el Python de Hermes y el de los
> crons no siempre la tienen).

## Arquitectura

### Principios (heredados de hermes-sdd)
- **El orquestador no interpreta, el ejecutor no firma y el notario no decide.** Las puertas tienen botones y una ventana para deshacer. Publicar, hacer cambios técnicos y otras acciones irreversibles siempre pasan por una puerta.
- **Pipelines como datos (JSON), no `case` en bash.** Es la mejora que el análisis de hermes-sdd señala como la más rentable.
- **Capacidades por cliente.** Cada etapa declara qué necesita (`publicacion`, `gsc`, `bing`, `analitica`…) y solo corre si el cliente lo tiene. Así una misma pipeline sirve para una web nueva, una con repo, una en WordPress o una sin acceso.
- **El vigía no usa LLM**: el modelo solo despierta si cambia algo. **Fail-closed**: guardia en `pre_tool_call` y `approvals.deny`.
- Español en todo lo que ve una persona; inglés en los prompts de los ejecutores, como en hermes-sdd.

### Estructura del repo `hermes-seo/`
```
instalar.sh            # idempotente: copia a ~/.hermes/hermes-seo/<versión> + enlace actual, perfiles y plugin
cliente.sh             # alta | importar | estado | baja | config  (envoltorio de hseo_clientes.py)
lanzar.sh              # inicia una pipeline para un cliente: crea tarjetas en su tablero (lee pipelines/*.json)
etapa.sh               # ejecuta una etapa: comprueba capacidades, monta el prompt (contexto del cliente + lecciones) y lanza el ejecutor
puerta.sh  firmar.sh  decidir.sh   # puertas, notario y canal local (copiados de hermes-sdd y simplificados)
encargado.sh  encargado/{SOUL.md,guardia.py,wiki/SCHEMA.md}
executors/{claude.sh,hermes.sh,replay.sh}   # claude.sh generaliza claude-encargo (contrato JSON outcome)
pipelines/*.json       # alta, linea-base, estrategia, articulo, actualizacion, cambio-seo,
                       # radar, metricas-semanales, revision-mensual, visibilidad-ia, difusion, mantenimiento
adaptadores/
  publicacion/{repo-pr,wordpress,entrega}.sh   # contrato: preparar | verificar | publicar | revertir | estado
  analitica/{cloudflare,ga4,plausible,ninguna}.py
  busqueda/{gsc,bing}.py                        # gsc vía el MCP `seo` (varias propiedades)
herramientas/          # auditoria-web, demanda-bing, enlaces-bing, sitemaps-competencia, brave-busca,
                       # chatgpt-busca, bots-ia, guardar-gsc, citas-ia… todas con --cliente <slug>
skills/                # genéricas, parametrizadas por el contexto del cliente (radar, investigacion,
                       # redactar, verificar, revision-lectura, metricas, revision-mensual, visibilidad-ia,
                       # difusion, auditoria-inicial, estrategia/mapa-tematico, wiki-global)
perfiles/              # SOUL de los perfiles de rol (seo-investigador, seo-redactor, seo-verificador,
                       # seo-editor, seo-analista) y de la coordinadora (Cartera)
plugin/hermes-seo/     # __init__.py (Telegram + comandos + prompt section), hseo_nucleo.py (puertas),
                       # hseo_clientes.py (alta, estado, vigía, foto), hseo_datos.py (telemetría),
                       # hseo_lecciones.py, hseo_revision.py, dashboard/ (pestaña «SEO»), ui/
plantillas/cliente.json   tests/   docs/   README.md   LICENSE
```

### El cliente (`~/.hermes/hermes-seo/clientes/<slug>/`, solo en la máquina de Hermes)
- **`cliente.json`**, validado por un esquema:
  - **identidad:** `dominio`, `idioma`, `mercados` (Bing, Brave, ChatGPT), `zona_horaria`, `persona_decide`;
  - **negocio:** `publico`, `voz` y `objetivo` (embudo opcional);
  - **`estado_web`:** `nueva | repo | wordpress | sin-acceso`;
  - **capacidades:**
    - `publicacion` (adaptador y sus parámetros: repo, rama, comandos de verificar y desplegar, URL de WordPress…);
    - `busqueda` (propiedad de GSC, sitio de Bing);
    - `analitica`;
    - `difusion`;
  - **`competidores`**, **`preguntas_ia`**;
  - **`politicas`**: congelación, tope semanal, `PARADO`, excepciones y bloqueos de publicación como `antes_de_publicar`;
  - **`telegram`:** `chat_id` y `thread_id`;
  - **`crons`** (activar o desactivar y horarios);
  - **`extensiones`**.
- **`secretos.env`** (600): las claves del cliente. Las globales, como Brave y OpenAI, van en `~/.hermes/hermes-seo/secretos.env`.
- **`wiki/`:** llm-wiki del cliente, con git propio.
- **`datos/`:** fotos diarias y `metricas.db` (SQLite) con series de GSC, Bing, analítica, bots de IA, visibilidad en IA y enlaces.
- **`informes/`, `briefs/`, `logs/`, `wt/`:** worktrees si la publicación es por repo.
- **`cambios.jsonl`:** cada cambio con su clase, hipótesis, URLs y fecha.
- **`extensiones/`:** skills, scripts, pipelines y crons propios del cliente.

### Ciclo de vida (pipelines)
| Fase | Pipeline | Puerta |
|---|---|---|
| 0. Alta | `alta`: crea el cliente, detecta `estado_web`, comprueba las capacidades (GSC, Bing, sitemap, robots, analítica, IndexNow) y prepara la lista de lo que falta | **Alta**: lista para dar por completado lo que tiene que hacer una persona |
| 1. Base técnica | `linea-base`: auditoría inicial, indexación y primera foto de datos; en una web nueva, recomendaciones de estructura, sitemap, schema y llms.txt | **Plan técnico** |
| 2. Estrategia | `estrategia`: mercado y keywords (Bing y Brave), competencia y mapa temático anticanibalización en la wiki | **Plan editorial** |
| 3. Producción | `articulo` / `actualizacion` / `cambio-seo`: investigar → redactar → verificar → revisión de lectura → preparar | **Publicar** (el adaptador ejecuta) |
| 4. Difusión | `difusion`: destinos y textos | Por destino |
| 5. Telemetría | crons de recogida sin LLM → `metricas.db` | — |
| 6. Decisión | `metricas-semanales`, `revision-mensual` y `visibilidad-ia`, con 3 encargos como mucho; a los 28 días, comparativa de cada cambio (con datos, sin veredicto automático) | **Decisión** / **Veredicto** |
| 7. Mantenimiento | `mantenimiento` diario por umbrales: caídas, noindex, sitemap, enlaces rotos, posiciones que caen | **Mantenimiento** (lanzar arreglo o ignorar con motivo) |

**Adaptadores de publicación:**
- **`repo-pr`:** worktree, PR en borrador, verificación con los comandos del `cliente.json`, despliegue con su script y merge.
- **`wordpress`:** REST API con contraseña de aplicación o MCP de WordPress; crea un borrador y lo publica cambiando el estado.
- **`entrega`:** web sin acceso. Genera un paquete (documento o Markdown con los cambios exactos) para que lo aplique otra persona; el cliente lo confirma en la puerta y se mide igual.

### Perfiles de Hermes
- **De rol, globales** (los crea `instalar.sh` sin borrar `.env` ni `mcp-tokens`): `seo-investigador`, `seo-redactor`, `seo-verificador`, `seo-editor` y `seo-analista`. `seo-analista` ya existe y conserva el OAuth del MCP `seo`. Saben de qué cliente se trata gracias a una sección de prompt del plugin que lee el tablero (`HERMES_KANBAN_BOARD`) y vuelca `cliente.json`, voz y público, un resumen de su wiki y las lecciones.
- **Encargado por cliente:** `seo-p-<slug>`. Copia el patrón de hermes-sdd:
  - SOUL plantilla y Sonnet;
  - `guardia.py` con lista blanca;
  - `WIKI_PATH=<cliente>/wiki`;
  - cron vigía `every 5m --monitor-script`;
  - su tema por `gateway.profile_routes`;
  - foto del estado con `register_system_prompt_section`.

  Además **asume el papel de coordinadora de su cliente** (ver «La coordinadora»): traduce los avisos de las tareas (`avisarme` con el encargado como notifier), muestra las puertas y propone o lanza encargos. Nunca decide ni publica: publicar es una puerta.
- **`default`:** coordinadora de la **Cartera**. Responde en el chat principal y en «📊 Cartera», opera todos los clientes y da de alta los nuevos.

### La coordinadora: se habla con ella y ella opera el sistema
Es el papel que haría Claude Code en una sesión con quien dirige: la persona pide en lenguaje natural («da de alta esta web», «¿cómo va X?», «escríbeme sobre Y», «revisa por qué cayeron los clics», «pon a Jev en auto para X») y ella lo traduce en acciones del sistema. La persona nunca necesita tocar la CLI.
- **Quién:** `default` en el chat principal y en «📊 Cartera», con todos los clientes. En el tema «🧭 cliente» habla el encargado `seo-p-<slug>`, con el mismo papel pero limitado a su cliente. Los dos tienen memoria: la global y la wiki del cliente.
- **Cómo opera:** **solo con la CLI `hseo`**, con lista de órdenes, argumentos validados, modo `--seco` y registro en `acciones.jsonl`. Es la versión ampliada de `encargado.sh` de hermes-sdd. Nunca usa bash libre sobre el sistema: lo impiden `guardia.py` (lista blanca) y `approvals.deny`.
- **Tres niveles de autonomía, impuestos por el guardia:**

  | Nivel | Acciones `hseo …` |
  |---|---|
  | **Sola** (y lo cuenta) | `estado`, `informe`, `datos consultar`, `lanzar <pipeline>` de análisis (radar, métricas, auditoría, visibilidad), `brief`, `escribir` (abre la cadena; la publicación es una puerta), `reintentar` una vez, `limpiar`, `apartar`, escribir en las wikis y `leccion proponer` |
  | **Con aprobación** (el guardia devuelve `approve` y Hermes pregunta a la persona con botones) | `cliente alta` y `cliente config` (incluye `estado_web` y capacidades), `jev modo`, `modelos`, `cron activar/desactivar`, pipelines con coste fijo (rondas de ChatGPT de pago), `relanzar` trabajo ya hecho |
  | **Nunca** | decidir o firmar puertas, publicar o desplegar fuera de una puerta, tocar `secretos.env`, `aprobadores.json` y el código del plugin |
- **Cuándo pregunta:** usa `clarify` con la opción recomendada primera y 5 preguntas como mucho, como en la preparación de hermes-sdd. Lo que ya pregunta una puerta no lo vuelve a preguntar.
- **Alta guiada:** «🧭 Preparar» de hermes-sdd aplicado a una web. Recoge el dominio y los accesos, detecta `estado_web`, pregunta lo que falte (público, mercados, objetivo y competidores) y lanza `alta`.

### Qué modelo hace cada etapa (copiado de `hsdd_proyectos.py` y `docs/ejecutores.md`)
- **`ETAPAS_MODELO` de SEO:** `estrategia`, `investigar`, `redactar`, `verificar`, `revisar-lectura`, `cambio-seo`, `metricas`, `revision-mensual`, `visibilidad`, `radar`, `difusion`, `auditoria`, `alta`.
- **`_PIENSAN`** (juicio, donde rinde un modelo grande): estrategia, redactar, revision-mensual y alta.
- **Perfiles de modelos:** `calidad` (Opus en todo), `equilibrado` (por defecto: Opus en las que piensan y Sonnet en el resto) y `rapido` (Sonnet). Alias `fable|opus|sonnet|haiku` con la familia más reciente, o un id completo. Por encima van `modelos.<etapa>` globales (`~/.hermes/hermes-seo/seo.json`) y después los del cliente (`cliente.json → modelos`), que mandan.
- **Ejecutor por etapa** (`ejecutor` y `ejecutores.<etapa>`):
  - `claude`: `claude -p` con el supervisor de `executors/claude.sh`, para la prosa y los cambios en el repo;
  - `hermes`: un perfil de rol con el modelo de su proveedor, para lo ligero y las herramientas MCP como GSC;
  - `replay`: pruebas sin coste.

  `modelo_para(etapa, ejecutor)` traduce el alias al formato de cada ejecutor. La traducción respeta el proveedor del perfil (OpenRouter, Anthropic con OAuth, etc.).
- **Lección de hermes-sdd:** nada de Haiku en juicios que acaben en probabilidad. Coste y minutos de cada etapa van a `etapas.jsonl`, para medir y ajustar el perfil.
- Se elige en el panel (Configuración → Modelos), con `/modelos` o pidiéndoselo a la coordinadora (nivel con aprobación).

### Jev en las puertas (copiado de `hsdd_nucleo.py`, `jev.sh`, `jev_puertas.json` y `docs/jev.md`)
- **Modos por cliente**, en `~/.hermes/hermes-seo/jev.json` (fuera del alcance de los agentes):
  - `humano`: Jev no interviene;
  - `consejo`: recomienda y decide una persona;
  - `piloto`: decide las puertas de la lista `piloto` (por defecto `plan-editorial` y `veredicto`);
  - `auto`: decide cualquier puerta.
- **Umbrales:** `umbral` 0.9 y `umbral_auto` 0.8 (entre 0.5 y 1). **Si no está seguro, la puerta va a la persona.**
- **Lo que Jev nunca hace:**
  - elegir opciones con texto, es decir, rechazar o pedir cambios;
  - decidir con un bloqueo o con un aviso grave de la revisión mecánica;
  - decidir si una persona ya le deshizo una decisión en esa puerta;
  - decidir puertas que el tipo reserva a una persona: la `alta` (accesos) y la difusión en nombre de la persona.
- **Ventana para deshacer:** 60 s para Jev y 180 s para una persona. El notario registra «Jev (modo, p)» y nunca la atribuye a la persona.
- **`jev_puertas_seo.json`:** criterios en inglés por tipo de puerta, con `instructions`/`instructions_auto` y `persona`/`persona_auto`:
  - **plan-editorial:** cada pieza tiene demanda medida, no canibaliza el mapa y encaja en la estrategia;
  - **publicar:** verificación APROBADO, revisión de lectura sin graves, título, meta, enlaces y canonical correctos, y políticas del cliente cumplidas (congelación, ventanas en las que no se publica);
  - **cambio-tecnico:** reversible y con hipótesis medible;
  - **veredicto:** la decisión que proponen los datos antes/después;
  - **mantenimiento:** el hallazgo es real.

  `estado_jev` le pasa el borrador, la nota de verificación, el informe o los hallazgos, igual que hoy le pasa los requisitos y el informe de aceptación.
- **Se copia el cliente** `sdd-jev.mjs` (necesita `TYPESAFE_API_KEY` en el gateway) y `jev.sh probar|rejuzgar`. **Calibración antes de activar `auto`:** pasar a Jev puertas históricas reales (publicaciones aprobadas por una persona y copias con un defecto metido) y fijar los umbrales con esos datos, como se hizo en hermes-sdd.
- **Aviso de privacidad:** el texto de la puerta sale a `api.typesafe.ai`. En los clientes que no lo permitan, `jev.permitido: false` en su `cliente.json`.

### Memoria
- **Wiki del cliente** (llm-wiki): el dominio, el público, las decisiones y su porqué, el mapa temático, lo que funcionó y lo que no. Regla: enlazar, no copiar. Los datos se consultan en `metricas.db`.
- **Wiki global** `~/.hermes/hermes-seo/wiki/`: conocimiento SEO transversal y **lecciones confirmadas**. La copia de `hseo_lecciones.py` funciona así:
  - la propuesta exige evidencia;
  - se confirma con ✅ o se descarta con 🗑 en Telegram;
  - se inyecta como mucho 5 veces en las etapas de otros clientes;
  - tras 3 usos, se pregunta si se mantiene o caduca.

  Los encargados la leen con una skill derivada, `wiki-global`, porque llm-wiki solo admite un `WIKI_PATH`. Solo escriben en ella a través de lecciones confirmadas.

### Panel: pestaña «SEO» en `hermes dashboard`
Secciones:
- **Cartera:** clientes, fase del ciclo, estado y próximas tareas.
- **Decisiones:** las mismas puertas que en Telegram.
- **Métricas:** gráficos por cliente desde `metricas.db`, como clics e impresiones a 28 días, consultas en las posiciones 8-20, bots de IA y visibilidad en IA.
- **Cambios:** hipótesis y comparación antes/después.
- **＋ Cliente:** asistente de alta.
- **Configuración.**

Se monta como en hermes-sdd: `dashboard/manifest.json`, `plugin_api.py` con FastAPI y `ui/` construido.

### Telegram
- **Comandos:** `/clientes`, `/estado [cliente]`, `/puertas`, `/alta <slug> <dominio>`, `/escribir [cliente] <tema>`, `/metricas [cliente]`, `/pausar`, `/reanudar`, `/lecciones`.
- **Temas:** «🧭 <cliente>» va al encargado y «📊 Cartera» a `default`.
- **Puertas:** botones `g:` (patrón de hermes-sdd) dentro del tema del cliente.

---
