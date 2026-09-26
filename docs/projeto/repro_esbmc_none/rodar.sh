#!/usr/bin/env bash
# Os casos *_ERRADO deveriam dar VERIFICATION FAILED (em CPython o assert falha).
cd "$(dirname "$0")"
esbmc --version
for f in *.py; do
  printf "%-28s " "$f"
  esbmc "$f" 2>&1 | grep "^VERIFICATION" || echo "(sem veredito)"
done
