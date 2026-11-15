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
| v2 · Entrega 4 | Visibilidad en IA mensual, cuaderno del método y costes, novedades y puerta `mejora` | ⏳ |

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
