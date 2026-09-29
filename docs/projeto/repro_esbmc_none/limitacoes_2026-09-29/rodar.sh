#!/usr/bin/env bash
# Uso: ./rodar.sh [binario-esbmc]   (padrão: esbmc do PATH)
# Flags do motor verify do pipeline: --unwind 5 --multi-property (solver padrão, Bitwuzla).
# O 05 usa --incremental-bmc de propósito: é o que ele demonstra.
ESBMC="${1:-esbmc}"
cd "$(dirname "$0")"
"$ESBMC" --version
for f in [0-9]*.py; do
  flags="--unwind 5 --multi-property"
  case "$f" in 05_*) flags="--incremental-bmc --max-k-step 5 --multi-property" ;; esac
  out=$(timeout 300 "$ESBMC" $flags "$f" 2>&1)
  v=$(printf "%s\n" "$out" | awk '
    /^Violated property:/ {getline; getline a; sub(/^ +/, "", a); props = props (props ? "; " : "") a}
    /^VERIFICATION / {verdicts = verdicts (verdicts ? " + " : "") $2}
    (/^ERROR/ || /^[A-Z][A-Za-z]*Error: /) && !err {err = substr($0, 1, 100)}
    /^WARNING: Undefined function/ && !warn {warn = $0}
    END {
      if (err) print err
      else { s = verdicts; if (props) s = s " (" props ")"; if (warn) s = s " [" warn "]"; print s }
    }')
  printf "%-36s %s\n" "$f" "${v:-(sem veredito: timeout ou crash)}"
done
