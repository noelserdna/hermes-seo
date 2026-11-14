# Estado

| Fase | Qué | Estado |
|---|---|---|
| F0 | Repo, esqueleto, licencia, diseño, lanzador de pruebas | ✅ |
| F1 | Núcleo: clientes, pipelines como datos, encargos y etapas, ejecutores (Claude Code, Hermes), puertas + notario + deshacer, Jev, modelos por etapa, CLI `hseo` con tres niveles y guardia, plugin (Telegram, bucle, comandos, foto en el prompt), cartas de los perfiles, `instalar.sh` | ✅ |
| F2 | Herramientas de datos por cliente (auditoría, demanda y enlaces de Bing, sitemaps de la competencia, Brave, ChatGPT, Search Console, bots de IA) y 19 skills de etapa | ✅ |
| F3 | Publicación: `repo-pr`, `wordpress`, `entrega`, política «antes de publicar», `cambios.jsonl` | ✅ · analítica GA4 y Plausible: pendiente (hoy: Cloudflare con `bots-ia`) |
| F4 | Encargado por web (perfil, guardia, wiki propia y global, vigía sin IA, tema de Telegram, tareas periódicas), revisión mecánica en puertas, lecciones entre webs | ✅ |
| F5 | Telemetría (`metricas.db`, resumen 28/28, «página 2», antes/después de un cambio) y pestaña «SEO» del panel | ✅ |
| F6 | Instalación en un Hermes real y migración del primer cliente | ⏳ |
| F7 | Segundo cliente en otro estado (WordPress o sin acceso) | — |

## Pendiente de comprobar en un Hermes real (F6)
- Que un cron y un aviso de un perfil enrutado (`seo-p-<web>`) llegan a su tema por el bot compartido.
- Que `hermes -p <perfil> -z … -s <skill> -m <modelo>` carga las skills de `skills.external_dirs` en los perfiles de rol.
- Que la sección de prompt y la pestaña del panel se cargan desde `~/.hermes/plugins/hermes-seo`.
