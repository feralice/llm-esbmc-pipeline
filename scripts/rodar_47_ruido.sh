#!/bin/bash
# Mede o ruído entre repetições: os 47 bugs da disciplina no HEAD. A repetição 1 faz a detecção; as demais
# reaproveitam a detecção da 1 e refazem só a verificação (ruído da verificação). Sonnet pela assinatura, lições
# automáticas desligadas (rodada de medição). A detecção de 07/11 não serve: os prompts mudaram depois.
# Espera o scan noturno terminar para não dividir a cota. Retoma sozinha se a cota acabar (código 3).
# Uso: scripts/rodar_47_ruido.sh [repetições, padrão 2]
cd "$(dirname "$0")/.."
ulimit -v 8000000
DATA=$(date +%Y-%m-%d)
FIRST=artifacts/pgene601/ruido-$DATA-r1
D=dataset/disciplina_pgene601
ESBMC="$HOME/esbmc-master/build-bw/src/esbmc/esbmc"
while pgrep -f "main.py --mode scan" >/dev/null; do sleep 120; done
for rep in $(seq 1 "${1:-2}"); do
  OUT=artifacts/pgene601/ruido-$DATA-r$rep
  mkdir -p "$OUT"
  resume=()
  if [[ $rep -gt 1 && ! -f $OUT/v2_checkpoint.json ]]; then
    .venv/bin/python - "$FIRST/v2_checkpoint.json" "$OUT/v2_checkpoint.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
d["verify_results"], d["telemetry_events"] = {}, []
d.pop("interrupted_at", None); d.pop("interruption_reason", None)
json.dump(d, open(sys.argv[2], "w"))
PY
  fi
  [[ -f $OUT/v2_checkpoint.json ]] && resume=(--resume)
  { git rev-parse --short HEAD; "$ESBMC" --version | head -1; } > "$OUT/commit.txt" 2>&1
  for attempt in $(seq 1 20); do
    PYTHONPATH=src .venv/bin/python -W ignore::SyntaxWarning src/main.py --mode hybrid --v2-stage end-to-end \
      --input $D/funcao_com_bug --ground-truth $D/ground_truths.json \
      --verification-sources $D/arquivo_com_bug --fixed-sources $D/arquivo_corrigido \
      --v2-variants A1,A2 --backend claude_cli --model claude-sonnet-5-5 \
      --synth-backend claude_cli --synth-model claude-sonnet-5-5 --no-auto-lessons \
      --esbmc-command "$ESBMC" --bound 5 --timeout 180 \
      --output-dir "$OUT" "${resume[@]}" >> "$OUT/run.log" 2>&1
    code=$?
    echo "$(date -Is) r$rep tentativa $attempt saiu com $code" >> "$OUT/status.log"
    [[ -f $OUT/v2_verify_report.json ]] && ! grep -q '"verdict": "PIPELINE_ERROR"' "$OUT/v2_verify_report.json" && break
    [[ $code -eq 3 ]] || break
    [[ -f $OUT/v2_checkpoint.json ]] && resume=(--resume)
    sleep 1800
  done
done
echo "$(date -Is) fim" >> artifacts/pgene601/ruido-status.log
