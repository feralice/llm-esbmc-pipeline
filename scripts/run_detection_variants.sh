#!/usr/bin/env bash
# Detection-only runs of the V2 prompt variants, one after the other; each resumes after a usage
# limit or network error (up to 3 attempts), on the files of a fixed sample (v2_detection_sample.py).
# Usage: scripts/run_detection_variants.sh <tag> <sample.json> <variant>...
# A variant "A0-rN" is a repeat of the baseline prompt.
set -u
cd "$(dirname "$0")/.."
PY=${PY:-/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc/.venv/bin/python}
tag=$1; sample=$2; shift 2
mapfile -t files < <("$PY" -c 'import json,sys; print("\n".join(json.load(open(sys.argv[1]))["files"]))' "$sample")
for variant in "$@"; do
  out=artifacts/v2/det-$tag-$variant
  flags=()
  [[ $variant != A0* ]] && flags=(--v2-variants "$variant")
  for attempt in 1 2 3; do
    resume=()
    [[ -f $out/v2_checkpoint.json ]] && resume=(--resume)
    PYTHONPATH=src "$PY" src/main.py --mode hybrid --v2-stage detection \
      --input "${files[@]}" --ground-truth dataset/bugs_reais/ground_truths.json \
      --context-sources dataset/bugs_reais/arquivo_com_bug \
      --backend claude_cli --model claude-sonnet-5-5 "${flags[@]}" "${resume[@]}" \
      --output-dir "$out" >> "$out.log" 2>&1 && break
    sleep 600  # usage limit or network: wait before resuming
  done
  echo "$(date -Is) $variant exit $?" >> "artifacts/v2/det-$tag.status"
done
