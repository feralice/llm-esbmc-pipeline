#!/bin/bash
# Roda um scan da CLI e retoma do checkpoint quando a cota da assinatura acaba (código 3).
# Uso: scripts/scan_com_retomada.sh <repositório> <pasta de saída> [--limit N]
set -u
cd "$(dirname "$0")/.."
repo="$1"; out="$2"; shift 2
mkdir -p "$out"
for attempt in $(seq 1 30); do
  resume=()
  [[ -f $out/scan_checkpoint.json ]] && resume=(--resume)
  .venv/bin/llm-esbmc scan "$repo" --backend claude --yes --out "$out" "${resume[@]}" "$@" >> "$out/run.log" 2>&1
  code=$?
  echo "$(date -Is) tentativa $attempt saiu com $code" >> "$out/status.log"
  [[ $code -eq 0 ]] && break
  [[ $code -ne 3 ]] && break
  sleep 1800
done
echo "$(date -Is) fim" >> "$out/status.log"
