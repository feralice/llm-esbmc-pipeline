#!/usr/bin/env bash
# Roda o benchmark V1 para os 3 modelos principais.
# Uso: bash scripts/run_v1_benchmark.sh [--skip-smells] [--dry-run]
#
# Requer:
#   OPENAI_API_KEY e ANTHROPIC_API_KEY definidas no ambiente
#   Ollama rodando: ollama serve  (para qwen2.5-coder:7b)
#   qwen baixado:   ollama pull qwen2.5-coder:7b

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# --- modelos fixados para reprodutibilidade ---
MODELS=(
    "gpt-4o-2024-11-20"
    "claude-3-5-sonnet-20241022"
    "qwen2.5-coder:7b"
)

GT_BUGS="dataset/labeled/ground_truths/bugs"
GT_SMELLS="dataset/labeled/ground_truths/smells"
OUT_DIR="reports/json/v1_benchmark"
BOUND=5
TIMEOUT=30

SKIP_SMELLS=false
DRY_RUN=false
for arg in "$@"; do
    case $arg in
        --skip-smells) SKIP_SMELLS=true ;;
        --dry-run)     DRY_RUN=true ;;
    esac
done

mkdir -p "$OUT_DIR"

run_benchmark() {
    local model="$1"
    local gt="$2"
    local suffix="$3"
    local safe_name
    safe_name=$(echo "$model" | tr ':/-' '_' | tr -s '_')
    local report="$OUT_DIR/benchmark_${safe_name}_${suffix}.json"

    echo ""
    echo ">>> modelo: $model  |  gt: $gt  |  saída: $report"

    if $DRY_RUN; then
        echo "    [dry-run] pulando execução"
        return 0
    fi

    python3 src/main.py \
        --mode benchmark \
        --input "$gt" \
        --model "$model" \
        --bound "$BOUND" \
        --timeout "$TIMEOUT" \
        --report "$report"
}

echo "========================================"
echo "  V1 Benchmark — $(date '+%Y-%m-%d %H:%M')"
echo "  Modelos: ${MODELS[*]}"
echo "  Bound: $BOUND  Timeout: ${TIMEOUT}s"
echo "========================================"

# --- bugs (tabela principal do artigo) ---
echo ""
echo "=== BUGS ==="
for model in "${MODELS[@]}"; do
    run_benchmark "$model" "$GT_BUGS" "bugs"
done

# --- smells ---
if ! $SKIP_SMELLS; then
    echo ""
    echo "=== SMELLS ==="
    for model in "${MODELS[@]}"; do
        run_benchmark "$model" "$GT_SMELLS" "smells"
    done
fi

echo ""
echo "========================================"
echo "  Concluído. Relatórios em: $OUT_DIR"
echo "  Para ver a tabela comparativa:"
echo "  python3 scripts/compare_benchmarks.py --dir $OUT_DIR"
echo "========================================"
