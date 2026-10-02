#!/usr/bin/env bash
# Repeats the RQ2 repair-vs-resample comparison (same budget) to measure run-to-run variation.
# Usage: scripts/run_repair_experiment.sh <first_rep> <last_rep>   e.g. 2 3
# Runs are sequential and capped at 8 GB: parallel unbounded ESBMC runs exhausted WSL memory.
set -u
cd "$(dirname "$0")/.."
run() {  # strategy rep
  local out="artifacts/v2/exp-oracle-$1-rep$2" resume=()
  [ -f "$out/v2_checkpoint.json" ] && resume=(--resume)
  ( ulimit -v 8388608
    PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src .venv/bin/python -u src/main.py --mode hybrid --v2-stage synthesis \
      --spec-strategy "$1" --input dataset/bugs_reais/funcao_com_bug \
      --ground-truth dataset/bugs_reais/ground_truths.json --model gpt-4o-mini --synth-backend openai \
      --synth-model gpt-4o-mini --verification-sources dataset/bugs_reais/arquivo_com_bug --bound 5 --timeout 180 \
      --output-dir "$out" "${resume[@]}" ) >> "$out.log" 2>&1
  echo "$1 rep $2 exit $?"
}
for rep in $(seq "$1" "$2"); do
  run repair "$rep"
  run resample "$rep"
done
