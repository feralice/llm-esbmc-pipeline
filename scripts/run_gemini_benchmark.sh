#!/usr/bin/env bash
# Tenta modelos Gemini em ordem até um completar o benchmark com sucesso.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GROUND_TRUTH="${1:-dataset/labeled/ground_truths}"
OUT_DIR="${2:-reports/json/v1_benchmark}"
BOUND="${3:-5}"
TIMEOUT="${4:-30}"

MODELS=(
    "gemini-2.5-flash"
    "gemini-2.5-flash-lite"
    "gemini-2.0-flash"
    "gemini-2.0-flash-lite"
    "gemini-1.5-flash"
    "gemini-1.5-flash-8b"
)

mkdir -p "$ROOT/$OUT_DIR"

for model in "${MODELS[@]}"; do
    safe="${model//./_}"
    safe="${safe//-/_}"
    report="$ROOT/$OUT_DIR/benchmark_${model}.json"

    echo ""
    echo "========================================"
    echo "Tentando modelo: $model"
    echo "========================================"

    set +e
    python3 "$ROOT/src/main.py" \
        --mode benchmark \
        --input "$GROUND_TRUTH" \
        --model "$model" \
        --backend google \
        --bound "$BOUND" \
        --timeout "$TIMEOUT" \
        --report "$report"
    exit_code=$?
    set -e

    if [ $exit_code -eq 0 ]; then
        echo ""
        echo "OK: $model concluiu. Relatório: $report"
        exit 0
    else
        echo ""
        echo "FALHOU ($exit_code): $model — tentando próximo..."
    fi
done

echo ""
echo "ERRO: Nenhum modelo Gemini funcionou. Verifique GEMINI_API_KEY e cota."
exit 1
