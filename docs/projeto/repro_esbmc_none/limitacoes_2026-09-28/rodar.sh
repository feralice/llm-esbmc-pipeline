#!/usr/bin/env bash
# Uso: ./rodar.sh [binario-esbmc]   (padrão: esbmc do PATH)
ESBMC="${1:-esbmc}"
cd "$(dirname "$0")"
"$ESBMC" --version
for f in [0-9]*.py; do
  v=$("$ESBMC" --z3 --unwind 6 --timeout 120s "$f" 2>&1 | awk '
    /^Violated property:/ {getline; getline a; sub(/^ +/, "", a); print "FAILED: " a; exit}
    /VERIFICATION SUCCESSFUL/ {print "SUCCESSFUL"; exit}
    /ERROR/ {print substr($0, 1, 90); exit}
    /Timed out/ {print "TIMEOUT"; exit}')
  printf "%-18s %s\n" "$f" "$v"
done
