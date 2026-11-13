#!/bin/bash
# Varre repositórios em sequência com Haiku e retoma do checkpoint quando a cota acaba (código 3).
# Uso: [TENTATIVAS=1] scripts/scan_noite.sh <pasta de saída base> <repo> [<repo> ...]   (repos em ~/alvos)
# TENTATIVAS=1: para quando a cota acaba, sem esperar a renovação (preserva a cota do dia seguinte).
set -u
cd "$(dirname "$0")/.."
base="$1"; shift
for name in "$@"; do
  out="$base/${name}_$(date +%Y-%m-%d)"
  mkdir -p "$out"
  for attempt in $(seq 1 "${TENTATIVAS:-30}"); do
    resume=()
    [[ -f $out/scan_checkpoint.json ]] && resume=(--resume)
    ulimit -c 0
    TMPDIR=/mnt/e .venv/bin/python src/main.py --mode scan --input "$HOME/alvos/$name" --output-dir "$out" \
      --backend claude_cli --model haiku --synth-model haiku --scan-rank pagerank --scan-limit 15 --v2-variants A1,A2,A12,A22 \
      --bound 5 --timeout 180 --operational-retries 2 --yes "${resume[@]}" >> "$out/run.log" 2>&1
    code=$?
    echo "$(date -Is) $name tentativa $attempt saiu com $code" >> "$out/status.log"
    [[ $code -eq 3 ]] || break
    sleep 1800
  done
done
echo "$(date -Is) fim" >> "$base/status_geral.log"
pastas=()
for name in "$@"; do pastas+=("$base/${name}_$(date +%Y-%m-%d)"); done
.venv/bin/python scripts/relatorio_scans.py "${pastas[@]}" --out "$base/RELATORIO_$(date +%Y-%m-%d).md" >> "$base/status_geral.log" 2>&1
