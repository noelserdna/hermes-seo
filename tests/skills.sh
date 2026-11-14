#!/usr/bin/env bash
# Cada skill que usa una pipeline existe, con su nombre en el frontmatter; las cartas de los perfiles existen.
set -uo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
fail=0; ok() { echo "ok   $1"; }; bad() { echo "FAIL $1"; fail=1; }
for s in $(jq -r '.etapas[].skill' "$ROOT"/pipelines/*.json | sort -u); do
  f="$ROOT/skills/$s/SKILL.md"
  if [ -f "$f" ] && grep -q "^name: $s$" "$f" && grep -q '^description: ' "$f"; then ok "skill $s"; else bad "falta o está mal la skill $s"; fi
done
for p in $(jq -r '.etapas[].perfil' "$ROOT"/pipelines/*.json | sort -u) seo-estacion comun coordinadora; do
  [ -s "$ROOT/perfiles/$p.md" ] && ok "carta $p" || bad "falta la carta $p"
done
for s in "$ROOT"/skills/*/SKILL.md; do
  n=$(basename "$(dirname "$s")")
  jq -r '.etapas[].skill' "$ROOT"/pipelines/*.json | grep -qx "$n" || bad "skill $n sin pipeline que la use"
done
grep -rIl "desarrollomcp\|Andrés\|Nortia" "$ROOT/skills" "$ROOT/perfiles" "$ROOT/encargado" && bad "datos de un cliente concreto en skills o cartas" || ok "skills y cartas sin datos de un cliente concreto"
exit $fail
