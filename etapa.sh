#!/usr/bin/env bash
# Ejecuta UNA etapa de un encargo. Lo llama la estación (perfil seo-estacion) desde el cuerpo de la tarjeta:
#   etapa.sh <cliente> <encargo> <etapa>
# Última línea de stdout: JSON {outcome: done|failed|scheduled|busy, reason, resumen, puerta…} (ver hseo_etapa.py).
ROOT="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$ROOT/plugin/hermes-seo/hseo_etapa.py" "$@"
