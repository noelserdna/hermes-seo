# hermes-seo

**El SEO de tus webs, de la puesta en marcha a la decisión, con agentes de IA y sin perder el control.** Hablas con
una coordinadora (en Telegram o en el panel de Hermes): le pides cosas y ella mueve el sistema. Los agentes investigan,
escriben, verifican, miden y proponen; lo irreversible (publicar, cambios técnicos, decisiones de estrategia) pasa por
una **puerta** que decides tú con un botón, o Jev si se lo delegas y está seguro.

Es un plugin para [Hermes Agent](https://github.com/NousResearch/hermes-agent), hermano de
[hermes-sdd](https://github.com/noelserdna/hermes-sdd) (el mismo esqueleto: puertas, notario, encargado por proyecto,
vigía sin IA, memoria con llm-wiki), aplicado al SEO.

> **Estado:** núcleo completo y probado sin IA (`bash tests/todo.sh`); falta la primera instalación en un Hermes de
> producción. Diseño en [docs/diseno.md](docs/diseno.md); fases y pendientes en [docs/estado.md](docs/estado.md).

## La idea en una tabla

| Papel | Quién | Qué hace |
|---|---|---|
| **Conversa y opera** | la coordinadora (perfil `default`) y un encargado por web (`seo-p-<web>`) | entiende lo que pides, lanza el trabajo con la CLI `hseo`, vigila, recuerda y te avisa |
| **Hace el trabajo** | perfiles de rol (`seo-investigador`, `seo-redactor`, `seo-verificador`, `seo-editor`, `seo-analista`) y Claude Code | cada etapa de una pipeline, con el modelo que le toca |
| **Pregunta** | la puerta | te enseña el resultado y te pide una decisión con botones |
| **Decide** | tú, o Jev (TypeSafe) en el modo que elijas por web | Jev solo aprueba, y solo si está seguro; si duda, te la pasa a ti |
| **Firma** | el notario (sin IA) | registra quién decidió qué y ejecuta lo aprobado (publicar, desplegar…) |
| **Orquesta** | el kanban de Hermes (sin IA) | un tablero por web |

## Cada web es un cliente

Una web, en el estado en que esté:

| Estado | Cómo se publica |
|---|---|
| `nueva` | se diseña la base técnica y la estrategia desde cero |
| `repo` | PR en borrador → verificación → despliegue (adaptador `repo-pr`) |
| `wordpress` | borrador en WordPress por su API → publicar (adaptador `wordpress`) |
| `sin-acceso` | un paquete con los cambios exactos para quien lleve la web (adaptador `entrega`) |

Sus datos (configuración, claves, wiki, métricas) viven solo en la máquina de Hermes, en
`~/.hermes/hermes-seo/clientes/<web>/`, nunca en este repositorio.

## El ciclo de vida

```
alta → línea base técnica → estrategia y mapa temático → producción → publicación → difusión
                                     ▲                                                    │
                                     └── decisión ◀── telemetría (GSC, Bing, analítica, IA) ◀┘
```

## Instalación

```bash
git clone https://github.com/noelserdna/hermes-seo && cd hermes-seo
bash tests/todo.sh                 # todas las pruebas, sin IA ni red
bash instalar.sh                   # arnés, plugin, CLI hseo y perfiles (no toca tu perfil principal)
bash instalar.sh --coordinadora    # opcional: convierte el perfil principal en la coordinadora del SEO
hermes gateway restart
```

Después, en Telegram o en el panel, a la coordinadora: «da de alta mi web ejemplo.com». Ella pregunta lo que falte,
pide tu aprobación y lanza la comprobación inicial. Para hablar con el encargado de una web: `/seo_tema <web>`.

| Comando de Telegram | Para qué |
|---|---|
| `/seo [web]` | cómo va todo |
| `/seo_puertas` | decisiones pendientes, con sus botones |
| `/seo_jev [web] [modo]` | modo de Jev: humano, consejo, piloto, auto |
| `/seo_tema <web>` | un tema para hablar con el encargado de esa web |
| `/seo_pausar` · `/seo_reanudar` `[web\|todo]` | parar y seguir |

## Estructura

| Ruta | Qué es |
|---|---|
| `plugin/hermes-seo/` | el plugin: clientes, pipelines, encargos, etapas, puertas y Jev, publicación, datos, lecciones, revisión, CLI, Telegram y la pestaña del panel (`dashboard/`) |
| `pipelines/` | el ciclo de vida como datos (JSON) |
| `skills/` | lo que hace cada etapa |
| `herramientas/` | datos de solo lectura por web (Search Console, Bing, Brave, ChatGPT, auditoría…) |
| `perfiles/`, `encargado/` | cartas de los perfiles, guardia, plantilla del encargado y de su wiki |
| `executors/` | Claude Code (con supervisor) y Hermes |
| `instalar.sh`, `encargado.sh`, `etapa.sh`, `hseo` | instalación, encargados, ejecución de una etapa y la CLI |

Licencia MIT.
