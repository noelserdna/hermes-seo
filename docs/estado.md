# Estado

| Fase | Qué | Estado |
|---|---|---|
| F0 | Repo, esqueleto, licencia, diseño, lanzador de pruebas | ✅ |
| F1 | Núcleo: clientes, pipelines como datos, encargos y etapas, ejecutores (Claude Code, Hermes), puertas + notario + deshacer, modelos por etapa, CLI `hseo` con tres niveles y guardia, plugin (Telegram, bucle, comandos, foto en el prompt), cartas de los perfiles, `instalar.sh` | ✅ |
| F2 | Herramientas de datos por cliente (auditoría, demanda y enlaces de Bing, sitemaps de la competencia, Brave, ChatGPT, Search Console, bots de IA) y skills de etapa | ✅ |
| F3 | Publicación: `repo-pr`, `wordpress`, `entrega`, política «antes de publicar», `cambios.jsonl` | ✅ · analítica GA4 y Plausible: pendiente |
| F4 | Encargado por web (perfil, guardia, wiki, tema de Telegram, tareas periódicas), revisión mecánica en puertas | ✅ |
| F5 | Telemetría (`metricas.db`, resumen 28/28, «página 2», antes/después) y pestaña «SEO» del panel (solo lectura) | ✅ |
| F6 | Instalación en el Hermes del VPS y migración de desarrollomcp | ✅ 14-11 |
| v2 · Entrega 1 | Asegurar, limpiar, corregir, saber (ver abajo) | ✅ 15-11 |
| v2 · Entrega 2 | Memoria de la web sin modelo, tandas con control y veredicto, autoridad y presencia | ✅ 15-11 |
| v2 · Entrega 3 | Correo (buzón único en Cloudflare, botones con código) y aterrizaje guiado | ✅ 15-11 |
| v2 · Entrega 4 | Visibilidad en IA mensual, cuaderno del método y costes, novedades y puerta `mejora` | ✅ 15-11 |

## v2 · Entrega 1 (15-11-2026)
- **Asegurar:** `copia.sh` (copia diaria cifrada a R2, comprobada al subir), `latido/` (Worker de Cloudflare que avisa
  por Telegram desde fuera; el servidor reinicia el gateway una vez antes), `instalar.sh` por versión y commit +
  `volver.sh` (ensayado en vivo en los dos sentidos).
- **Limpiar:** fuera Jev; el panel no decide; con un aviso grave no se aprueba (`decidir-local --forzar MOTIVO`).
- **Ruido:** los informes no abren puerta; sin lanzamientos duplicados; máximo 3 decisiones por web; sin recordatorios.
- **Corregir:** una vuelta automática a redactar cuando la verificación pide cambios (`si_cambios`); crons
  reconciliados por nombre (reinstalar no cambia ids); despliegues fuera del cgroup del gateway; el resultado del
  despliegue contesta a la puerta (y con modo liga la reabre).
- **Saber:** estado real por turno (`pre_llm_call`) para el encargado y la coordinadora; parte semanal sin modelo
  (lunes 10:30) con hasta 3 propuestas y «haz la N» (`hseo propuesta`); datos con país, dispositivo, posición
  ponderada, `bajo_ctr` y marca; `prepara: ["resumen"]` (las cifras las pone el código).
- **Vigilar:** vigilancia sin modelo por web (`hseo_vigilancia`, cada 5 min: un intento de arreglo y aviso solo si
  sigue; probada en vivo) y salud del servidor fuera de Hermes (`hseo_sistema revisar` en el crontab; `avisos` en un
  cron sin IA). Fuera el vigía con modelo.
- **Coordinar:** `hseo preguntar|ordenar <web>` (sesión continua «coordinador» del encargado, registrada).
- **Guardia del encargado:** herramientas de una lista cerrada (matcher `.*`), sin aprobaciones, `--brief web otra`
  ya no engaña.

## v2 · Entrega 2 (15-11-2026)
- **Memoria de la web sin modelo** (`hseo_wiki`): páginas fijas `negocio`, `mapa-tematico`, `linea-base`,
  `decisiones`, `correcciones` y `cambios-y-veredictos`, escritas en su momento (configuración, cierre de pipelines con
  «memoria», firma de cada puerta, publicación) e idempotentes; cada etapa recibe «## Memoria que te toca».
  `hseo wiki sembrar <web>`.
- **Tandas** (`hseo_tandas`, `hseo tanda …`): candidatas por código con control, ≤4 páginas, ≤40 % de impresiones en
  ventana, una página no se toca por otro lado; veredicto diario sin modelo (funcionó / no funcionó / no se puede saber;
  si empeoró, puerta para volver atrás). El parte propone la tanda siguiente.
- **Autoridad y presencia** (`hseo_autoridad`, pipeline `autoridad`, sustituye a difusión): dónde citan las IA y los
  buscadores a otros y no a la web; ≤4 gestiones; puerta «Todas / Solo algunas / No»; las tuyas en el parte hasta
  `hseo gestion hecha`. Cron mensual (día 2).

## v2 · Entrega 3 (15-11-2026)
- **Correo** (`correo/` Worker `hermes-correo` + `hseo_correo`): un buzón (`hermes_seo@leonbohorquez.dev`, regla de
  Email Routing al Worker) y envío desde el subdominio `seo.leonbohorquez.dev` (Email Sending, Reply-To al buzón). Solo
  entra lo auténtico (primera `Authentication-Results` de `mx.cloudflare.net` con `dmarc=pass`) y no automático. Cada
  web tiene un contacto único (`hseo contacto <web> <correo> --canal correo|ambos|telegram`); un correo auténtico desde
  él lo deja comprobado. Puertas con texto legible y botones `mailto:` con un código de un solo uso por opción: decide
  el código (remitente de esa web, puerta suya, contenido sin cambios), con confirmación y DESHACER (30 min); un «sí»
  suelto o el texto libre van al encargado (sesión «correo»), que contesta en el hilo. Parte, incidencias y resultados
  también por correo. Probado en vivo el 15-11 (entrega, respuesta del encargado, descartar por botón).
- **Aterrizaje guiado** (`hseo_aterrizaje`, `hseo aterrizaje …`): 10 pasos que se comprueban solos; ningún cron arranca
  sin su acceso comprobado (las webs anteriores, «legado», no cambian); con los mínimos (1, 2, 3, 5) se lanza la línea
  base una vez y al cerrarla la estrategia; la vigilancia lo vuelve a comprobar cada 30 min y cuenta los cambios.
  `alta` pasa a informe. Claves solo por terminal (`hseo secreto guardar`).

## v2 · Entrega 4 (15-11-2026)
- **Visibilidad en IA:** `chatgpt-busca` distingue sin saldo (para, código 3) de ritmo (espera Retry-After) y
  `--reanudar` solo pregunta lo que falta; `hseo ia resumen` (sin modelo): cita y mención por motor con intervalo de
  Wilson y «sube/baja» solo si no se solapan. Mensual por defecto.
- **Cuaderno del método** (`hseo cuaderno apuntar`, cron de la coordinadora lunes 07:00, sin mensaje): fallos por etapa,
  «la verificación pidió cambios», puertas y horas hasta decidir, incidencias, correos, coste por web y por perfil;
  solo método, en la wiki global (`concepts/metodo-cifras.md`).
- **Estar al día** (`hseo novedad …`, cron de la coordinadora día 3 09:00, con modelo): versiones sin fetch ni canary;
  lo que sube clics o citas llega como puerta «🆕 adoptar» del sistema (≤3 al mes; aprobar solo lo apunta); lo demás,
  a `novedades-descartadas.md`. Nunca actualiza ni instala.
- **Mejoras del plugin** (`hseo mejora proponer <rama>`): pruebas en verde, nada que toque lo que vigila al sistema ni
  pida reinicio, ≤3 al mes → puerta «⬆️ mejora»; aprobarla instala esa versión a una carpeta nueva (vuelta: volver.sh).
- Las puertas del sistema van al coordinador (cliente `__cartera__`, tema 📊 Cartera).

## Cómo se deshace cada cosa
| Qué | Cómo |
|---|---|
| Código del plugin | `bash ~/.hermes/hermes-seo/actual/volver.sh` (a la instalación anterior) o `volver.sh <carpeta>` |
| Crons y config de los perfiles | `volver.sh … --config ~/backups-hermes-seo/previo-v2-*.tgz` |
| Datos de las webs | copia diaria en R2 (`hermes-copias`, clave en `~/.config/hermes-seo/copia.key` y en el Mac) |
| Latido externo | `wrangler delete` del Worker `hermes-latido` y quitar la línea del crontab |
| Salud del servidor | quitar la línea `hseo_sistema.py revisar` del crontab y el cron `hseo-sistema` |
| Correo | quitar la regla «hermes-seo buzón» de Email Routing, el subdominio de envío y el Worker `hermes-correo`; `contacto.canal = telegram` |
| Publicaciones | no se deshacen solas: se revierte el PR (`hseo lanzar <web> cambio-seo --param que="Revertir el PR #N"`) |

## 15-11, tarde: puesta en marcha sin esperar

En DesarrolloMCP se lanzó a mano lo que iba a esperar a su fecha: datos, métricas, parte, cuaderno, novedades,
visibilidad en IA y autoridad. Aterrizaje probado con una web de laboratorio (borrada): con 0 pasos solo arranca la
vigilancia; sin Search Console no hay línea base; `omitir` solo admite 6, 7 y 8. Esta nota llegó por la puerta «mejora».

## 15-11, noche: primeras decisiones por correo y paso a solo correo

- Tres decisiones reales de Andrés por correo, todas publicadas (lección 04, #103 y la gestión de cifras del curso).
- Correo: asunto único por puerta, con fecha y hora en la zona de la web (con el mismo asunto, Gmail juntaba la puerta
  nueva con las viejas). Un código de una puerta ya sustituida contesta cuál vale. El tope diario (10) solo cuenta los
  textos libres: antes descartó en silencio un PUBLICAR válido.
- Pruebas negativas en vivo: remitente ajeno auténtico → «remitente desconocido»; contenido cambiado tras el correo →
  no decide y se reenvía. El From falsificado no se pudo enviar en vivo (Cloudflare lo rechaza, error 10202, y el puerto
  25 de salida está cerrado); lo cubre `autentico()` del Worker y su prueba.
- DesarrolloMCP pasa a `contacto.canal = correo` (`hseo_correo.py contacto <web> <correo> --canal correo`; para volver,
  `--canal ambos`). El tema de Telegram y `/seo_puertas` quedan de reserva.
- Queda por ver: una semana sin intervenir (cuaderno, métricas y parte del lunes) y un artículo de punta a punta.

## 16-11: primera alta real (HearMyTour) y webs que publican por su propio MCP

Prueba de punta a punta hablando con la coordinadora por Telegram. Fallos encontrados y arreglados:
- `hseo alta` ya lo hace todo con la aprobación: la web, su encargado (`encargado.sh crear`), la lista de 10 pasos y,
  con `--correo`, el contacto con su correo de confirmación. Antes la coordinadora no creaba el encargado («es
  instalación») y el alta se quedaba a medias. `--idiomas en,es` (el primero es el principal; nuevo campo `idiomas`).
- La plantilla no traía `negocio.conversion`, que el paso 1 exige. `hseo preguntas <web>` guarda las preguntas para la
  IA donde las leen las herramientas y el paso 8. Bing solo cuenta como conectado con su clave.
- `poner_contacto` conserva la comprobación si la dirección no cambia (antes la borraba).
- La carta de la coordinadora: mirar la web antes de preguntar, preguntar la analítica (no deducirla del HTML),
  conversión aparte del objetivo, no narrar mientras trabaja. Las skills que Hermes escriba sola en el perfil principal
  piden aprobación (`skills.write_approval`).
- Adaptador de publicación `mcp` y `hseo_mcp.py`: acceso por auth.md (`service_auth`: código de 6 cifras que aprueba
  una persona con acceso al panel; la aserción renueva el token 90 días), lectura solo con herramientas de lectura, y
  publicación del artículo con sus traducciones enlazadas al aprobarse la puerta. Pruebas: `tests/mcp.sh`.
- Segunda vuelta con la coordinadora (16-11, mañana): la recogida diaria de una web nueva esperaba al paso 5 (datos de
  Search Console), que solo trae esa misma recogida: nunca arrancaba. Ahora arranca en cuanto hay alguna fuente. El
  paso 5 distingue «el acceso funciona, Google aún no tiene datos» de un fallo real. `hseo config` vuelve a comprobar
  la lista de pasos. La carta: varios idiomas ya es un ajuste (`idiomas`); no prometer tareas periódicas que no existen.
  En Telegram, sin comentarios intermedios del modelo (`display.interim_assistant_messages false`).
- Contacto con etiqueta (`nombre+web@gmail.com`, para una segunda web de la misma persona): Gmail responde siempre desde
  la dirección principal. Ahora la web de un correo entrante sale del hilo (In-Reply-To frente a `enviados.jsonl`), del
  código de la puerta o de la dirección exacta; la identidad que decide es la dirección guardada de esa web.
- La lista de pasos de una web nueva no se volvía a comprobar sola: un paso que depende del tiempo (los primeros
  datos de Google) no se cerraba nunca, ni se lanzaban la línea base y la estrategia. Ahora la recogida diaria la
  comprueba (`hseo_datos.avanzar_aterrizaje`) y avisa por correo al contacto de lo que avanza.
