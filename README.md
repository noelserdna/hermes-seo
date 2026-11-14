# hermes-seo

**El SEO de tus webs, de la puesta en marcha a la decisión, con agentes de IA y sin perder el control.** Hablas con
una coordinadora (en Telegram o en el panel de Hermes): le pides cosas y ella mueve el sistema. Los agentes investigan,
escriben, verifican, miden y proponen; lo irreversible (publicar, cambios técnicos, decisiones de estrategia) pasa por
una **puerta** que decides tú con un botón, o Jev si se lo delegas y está seguro.

Es un plugin para [Hermes Agent](https://github.com/NousResearch/hermes-agent), hermano de
[hermes-sdd](https://github.com/noelserdna/hermes-sdd) (el mismo esqueleto: puertas, notario, encargado por proyecto,
vigía sin IA, memoria con llm-wiki), aplicado al SEO.

> **Estado: en construcción.** Diseño en [docs/diseno.md](docs/diseno.md). Las fases y lo hecho, en
> [docs/estado.md](docs/estado.md).

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

Licencia MIT.
