# Herramientas de datos

Scripts de solo lectura (no publican ni escriben en ninguna web). Todos piden `--cliente <slug>`, leen
`clientes/<slug>/cliente.json` y las claves de `secretos.env` (del cliente o global), y guardan bajo
`clientes/<slug>/datos/`. Salen con 2 si falta configuración y con 3 si falta la clave; nunca la imprimen.

| Herramienta | Clave | Datos |
|---|---|---|
| `auditoria-web` · auditoría técnica desde el sitemap (`--sitemap`, `auditoria.rutas_privadas`) | ninguna | `datos/auditoria/AAAA-MM-DD.md` |
| `demanda-bing "<consulta>"…` · búsquedas relacionadas por mercado | `BING_WEBMASTER_API_KEY` | `datos/demanda/AAAA-MM-DD.md` (se añade) |
| `enlaces-bing` · enlaces entrantes, nuevos y perdidos | `BING_WEBMASTER_API_KEY` | `datos/enlaces/AAAA-MM-DD.json` |
| `sitemaps-competencia` · páginas nuevas de `competidores` | ninguna | `datos/competencia/<dominio>.txt` |
| `brave-busca` · páginas indexadas en Brave y puesto en las preguntas de decisión | `BRAVE_SEARCH_API_KEY` | `datos/ia/brave-AAAA-MM-DD.json` |
| `chatgpt-busca` · respuestas de ChatGPT con buscador a las preguntas de decisión | `OPENAI_API_KEY` | `datos/ia/chatgpt-AAAA-MM-DD.json` |
| `claude-busca` · respuestas de Claude con búsqueda web (Claude Code) a las preguntas de decisión | `CLAUDE_CODE_OAUTH_TOKEN` (o la sesión de la máquina) | `datos/ia/claude-AAAA-MM-DD.json` |
| `guardar-gsc` · copia diaria de Search Console por un servidor MCP (`capacidades.busqueda.gsc_mcp`) | token OAuth del perfil de Hermes (`gsc_perfil`) | `datos/gsc/AAAA-MM-DD.json` |
| `bots-ia` · bots de IA y buscadores por User-Agent (Cloudflare) | `CLOUDFLARE_ANALYTICS_TOKEN` | `datos/bots/AAAA-MM-DD.md` |

Las preguntas de decisión van en `clientes/<slug>/preguntas-decision.md` (líneas «1. …»). Cada herramienta explica
sus opciones con `--help`. Para las pruebas, `HSEO_URL_BING`, `HSEO_URL_BRAVE`, `HSEO_URL_OPENAI`, `HSEO_URL_CF` y
`HSEO_GSC_MCP` cambian la dirección de cada API, y `HSEO_SIN_PAUSAS=1` quita las esperas (`tests/herramientas.sh`).
