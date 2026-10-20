#!/usr/bin/env bash
# The final V2 run, once, with the frozen pipeline: detection with prompt A5 (A1+A2), level-1 harness
# and ESBMC, the orchestrator on stuck results (CPython search + pinned input; agents only with
# ARMS=...,claude_agent), the same on the fixed versions as control, and the verdict validation.
# Each step resumes or is skipped when its output exists, so the script can be run again after a stop.
# Usage: scripts/run_final.sh <tag>      e.g. scripts/run_final.sh 2026-10-08
set -u
cd "$(dirname "$0")/.."
PY=${PY:-/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/.venv/bin/python}
ARMS=${ARMS:-dynamic,pinned}
OUT=artifacts/v2/final-$1
GT=dataset/bugs_reais/ground_truths.json
ulimit -v 8000000

step() { echo "$(date -Is) $*" | tee -a "$OUT.status"; }
mkdir -p "$OUT"

if [[ ! -f $OUT/v2_verify_report.json ]]; then
  step "1/5 detection + level 1"
  resume=()
  [[ -f $OUT/v2_checkpoint.json ]] && resume=(--resume)
  PYTHONPATH=src "$PY" src/main.py --mode hybrid --v2-stage end-to-end --v2-variants A1,A2 \
    --input dataset/bugs_reais/funcao_com_bug --ground-truth "$GT" \
    --verification-sources dataset/bugs_reais/arquivo_com_bug \
    --backend claude_cli --model claude-sonnet-5-5 --synth-backend claude_cli --synth-model claude-sonnet-5-5 \
    --bound 5 --timeout 180 --output-dir "$OUT" "${resume[@]}" >> "$OUT/run.log" 2>&1 || { step "1/5 failed"; exit 1; }
fi

if [[ ! -f $OUT/control/report_0of1.json ]]; then
  step "2/5 control on the fixed versions (saved specs, no LLM)"
  "$PY" scripts/v2_replay_specs.py "$OUT/v2_verify_report.json" --esbmc "${LLM_ESBMC:-$HOME/esbmc-master/esbmc.sh}" --timeout 180 \
    --sources dataset/bugs_reais/arquivo_corrigido --strict-sources --out "$OUT/control" >> "$OUT/run.log" 2>&1
fi

step "3/5 orchestrator on the control ($ARMS without agents)"
"$PY" scripts/v2_orchestrate.py "$OUT/control/report_0of1.json" --arms dynamic,pinned \
  --verification-sources dataset/bugs_reais/arquivo_corrigido --out "$OUT/orq-control" >> "$OUT/run.log" 2>&1

step "4/5 orchestrator ($ARMS)"
"$PY" scripts/v2_orchestrate.py "$OUT/v2_verify_report.json" --arms "$ARMS" \
  --agent-model claude-sonnet-5-5 --control "$OUT/orq-control/orchestrated.json" --out "$OUT/orq" >> "$OUT/run.log" 2>&1

step "5/5 validation"
"$PY" scripts/v2_validate.py "$OUT" --control "$OUT/control/report_0of1.json" --mutants >> "$OUT/run.log" 2>&1

step "done"
