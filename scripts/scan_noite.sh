#!/bin/bash
# Varre repositórios em sequência (padrão Haiku) e retoma do checkpoint quando a cota acaba (código 3).
# Uso: [TENTATIVAS=1] scripts/scan_noite.sh <pasta de saída base> <repo> [<repo> ...]   (repos em ~/alvos)
# MODELO (padrão haiku), PULAR (funções do ranking a pular, padrão 0), LIMITE (padrão 15), PREFILTRO=1 liga --scan-prefilter.
# Um repo pode ser caminho absoluto.
# TENTATIVAS=1: para quando a cota acaba, sem esperar a renovação (preserva a cota do dia seguinte).
set -u
cd "$(dirname "$0")/.."
base="$1"; shift
for name in "$@"; do
  alvo="$name"; [[ $name == /* ]] || alvo="$HOME/alvos/$name"
  name="$(basename "$name")"
  out="$base/${name}_$(date +%Y-%m-%d)"
  mkdir -p "$out"
  for attempt in $(seq 1 "${TENTATIVAS:-30}"); do
    resume=()
    prefiltro=(); [[ ${PREFILTRO:-0} == 1 ]] && prefiltro=(--scan-prefilter)
    [[ -f $out/scan_checkpoint.json ]] && resume=(--resume)
    ulimit -c 0
    TMPDIR=/mnt/e .venv/bin/python src/main.py --mode scan --input "$alvo" --output-dir "$out" \
      --backend claude_cli --model "${MODELO:-haiku}" --synth-model "${MODELO:-haiku}" --scan-rank pagerank \
      --scan-limit "${LIMITE:-15}" --scan-skip "${PULAR:-0}" "${prefiltro[@]}" --v2-variants A1,A2,A12,A22 \
      --bound 5 --timeout 180 --operational-retries 2 --yes "${resume[@]}" >> "$out/run.log" 2>&1
    code=$?
    echo "$(date -Is) $name tentativa $attempt saiu com $code" >> "$out/status.log"
    [[ $code -eq 3 ]] || break
    sleep 1800
  done
done
echo "$(date -Is) fim" >> "$base/status_geral.log"
pastas=()
for name in "$@"; do pastas+=("$base/$(basename "$name")_$(date +%Y-%m-%d)"); done
.venv/bin/python scripts/relatorio_scans.py "${pastas[@]}" --out "$base/RELATORIO_$(date +%Y-%m-%d).md" >> "$base/status_geral.log" 2>&1
