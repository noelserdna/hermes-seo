#!/usr/bin/env bash
# Estar al día y mejorar: versiones sin modelo (sin canary), novedades que llegan como puerta «adoptar» del sistema
# (tope 3 al mes) o se apuntan como descartadas; mejoras del plugin: pruebas, nada que toque lo que vigila al sistema,
# nada que pida reinicio, puerta «mejora» y su instalación (en seco).
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
T=$(mktemp -d); trap 'rm -rf "$T"' EXIT
export HERMES_SEO_HOME="$T/home" HOME="$T/casa" HSEO_SIN_SCOPE=1 HSEO_MEJORA_SECO=1 HERMES_SEO_DESHACER_S=0
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
si() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else bad "$1"; fi; }
P="$ROOT/plugin/hermes-seo"; H="python3 $P/hseo_cli.py"
git config --global user.name p >/dev/null 2>&1; git config --global user.email p@x >/dev/null 2>&1; git config --global init.defaultBranch main >/dev/null 2>&1
mkdir -p "$T/bin" "$HERMES_SEO_HOME"; printf '#!/bin/sh\necho "Hermes Agent v0.23.1 (2026.9.24)"\n' > "$T/bin/hermes"; chmod +x "$T/bin/hermes"; export HERMES_BIN="$T/bin/hermes"
git init -q --bare "$T/hermes.git"; git init -q "$T/h"; (cd "$T/h" && git commit -q --allow-empty -m a && git tag v0.23.1 && git tag v0.24.0 && git tag v0.25.0-canary.3 && git tag v2026.9.24 && git remote add origin "$T/hermes.git" && git push -q origin main --tags)
export HSEO_REPO_HERMES="$T/hermes.git" HSEO_REPO_PLUGIN="$T/hermes.git"
echo "{\"yo\":{\"nombre\":\"Yo\",\"canales\":{\"local\":\"$(id -un)\"},\"clientes\":[\"*\"]}}" > "$HERMES_SEO_HOME/aprobadores.json"
R=$($H novedad recoger)
echo "$R" | jq -e '.hermes.instalada == "0.23.1" and .hermes.ultima_estable == "0.24.0" and .hermes.hay_nueva' >/dev/null && ok "versiones: hay una estable nueva (ni la canary ni la etiqueta con fecha cuentan)" || bad "versiones ($R)"
si "una novedad que sube clics o citas llega como puerta «adoptar» del sistema" "$H novedad proponer 'Hermes 0.24' 'entrega de cron por tema' 'bajo' | grep -q 'Propuesta' && python3 $P/hseo_puertas.py listar | grep -q '__cartera__.*Novedad'"
$H novedad proponer b c d >/dev/null; $H novedad proponer e f g >/dev/null
si "más de 3 al mes: se apunta como descartada" "$H novedad proponer h i j | grep -q 'descartada' && grep -q 'tope de 3' $HERMES_SEO_HOME/wiki/concepts/novedades-descartadas.md"
G=$(python3 $P/hseo_puertas.py listar | grep -m1 Novedad | awk '{print $1}')
si "aprobar una novedad solo la apunta" "python3 $P/hseo_puertas.py decidir-local $G acepto | grep -q 'apuntada' && [ -s $HERMES_SEO_HOME/novedades/apuntadas.jsonl ]"
# mejoras: un repo del plugin de mentira
git init -q --bare "$T/plugin.git"; git init -q "$T/repo"
(cd "$T/repo" && mkdir -p tests skills/x encargado && printf '#!/bin/sh\necho "todo ok"\n' > tests/todo.sh && echo a > skills/x/SKILL.md && echo g > encargado/guardia.py \
  && git add -A && git commit -qm base && git remote add origin "$T/plugin.git" && git push -q origin main \
  && git checkout -qb buena && echo b >> skills/x/SKILL.md && git commit -qam buena && git push -q origin buena \
  && git checkout -qb mala main && echo h >> encargado/guardia.py && git commit -qam mala && git push -q origin mala \
  && git checkout -qb rompe main && printf '#!/bin/sh\necho FALLA; exit 1\n' > tests/todo.sh && echo c >> skills/x/SKILL.md && git commit -qam rompe && git push -q origin rompe)
export HSEO_REPO="$T/repo"
OUTM=$($H mejora proponer mala 2>&1); echo "$OUTM" | grep -q "vigila al propio sistema" && ok "una mejora que toca el guardia no se ofrece" || bad "guardia ($OUTM)"
si "una mejora con las pruebas en rojo no se ofrece" "! $H mejora proponer rompe"
si "una mejora de skills con pruebas en verde llega como puerta «mejora»" "$H mejora proponer buena | grep -q 'propuesta' && python3 $P/hseo_puertas.py listar | grep -q 'Mejora del sistema: buena'"
G=$(python3 $P/hseo_puertas.py listar | grep 'Mejora del sistema' | awk '{print $1}')
si "aprobarla la instala (en seco) y queda apuntado" "python3 $P/hseo_puertas.py decidir-local $G acepto | grep -q 'instalaría buena@' && grep -q '\"instalada\"' $HERMES_SEO_HOME/mejoras.jsonl"
exit $fail
