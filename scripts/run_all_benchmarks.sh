#!/usr/bin/env bash
# Benchmark paralelo: APIs (gemini/claude/gpt) rodam ao mesmo tempo.
# Ollama (qwen/deepseek) sequencial — VRAM compartilhada.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GROUND_TRUTH="${GROUND_TRUTH:-dataset/labeled/ground_truths}"
OUT_DIR="${OUT_DIR:-reports/json/v1_benchmark}"
BOUND="${BOUND:-5}"
TIMEOUT="${TIMEOUT:-30}"
LLM_TIMEOUT="${LLM_TIMEOUT:-300}"
LOG_DIR="$ROOT/logs/benchmark"

mkdir -p "$ROOT/$OUT_DIR" "$LOG_DIR"

# PIDs dos jobs paralelos de API
API_PIDS=()
API_NAMES=()

run_model_log() {
    local model="$1" backend="$2" logfile="$3"
    local safe_name report
    safe_name="$(echo "$model" | tr '/:.' '_' | tr -s '_' | sed 's/_$//')"
    report="$ROOT/$OUT_DIR/benchmark_${safe_name}.json"

    {
        echo "════════════════════════════════════════"
        echo "  Modelo : $model  [backend=$backend]"
        echo "  Report : $report"
        echo "════════════════════════════════════════"
        python3 "$ROOT/src/main.py" \
            --mode benchmark \
            --input "$GROUND_TRUTH" \
            --model "$model" \
            --backend "$backend" \
            --bound "$BOUND" \
            --timeout "$TIMEOUT" \
            --llm-timeout "$LLM_TIMEOUT" \
            --report "$report" \
            --verbose
        echo "EXIT:$?"
    } 2>&1 | tee "$logfile"
}

run_gemini_fallback_log() {
    local logfile="$1"
    local models=(
        "gemini-2.5-flash"
        "gemini-2.5-flash-lite"
        "gemini-2.0-flash"
        "gemini-2.0-flash-lite"
        "gemini-1.5-flash"
        "gemini-1.5-flash-8b"
    )
    for model in "${models[@]}"; do
        echo "" | tee -a "$logfile"
        echo "  [Gemini fallback] Tentando: $model" | tee -a "$logfile"
        local safe_name report
        safe_name="$(echo "$model" | tr '/:.' '_' | tr -s '_')"
        report="$ROOT/$OUT_DIR/benchmark_${safe_name}.json"
        python3 "$ROOT/src/main.py" \
            --mode benchmark \
            --input "$GROUND_TRUTH" \
            --model "$model" \
            --backend google \
            --bound "$BOUND" \
            --timeout "$TIMEOUT" \
            --llm-timeout "$LLM_TIMEOUT" \
            --report "$report" \
            --verbose >> "$logfile" 2>&1
        local rc=$?
        if [ $rc -eq 0 ]; then
            echo "  ✓ Gemini OK: $model" | tee -a "$logfile"
            return 0
        fi
        echo "  ✗ Falhou ($rc), tentando próximo..." | tee -a "$logfile"
    done
    echo "  ERRO: Nenhum modelo Gemini funcionou." | tee -a "$logfile"
    return 1
}

echo ""
echo "╔══════════════════════════════════════════╗"
echo "║   BENCHMARK V1 — PARALELO + SEQUENCIAL   ║"
echo "║  APIs: paralelo | Ollama: sequencial      ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Logs individuais em: $LOG_DIR/"
echo ""

# ── APIs em paralelo (background) ──────────────────────────────────────
echo "▶ Disparando APIs em paralelo..."

run_gemini_fallback_log "$LOG_DIR/gemini.log" &
API_PIDS+=($!); API_NAMES+=("gemini")

run_model_log "claude-sonnet-4-6" "anthropic" "$LOG_DIR/claude.log" &
API_PIDS+=($!); API_NAMES+=("claude-sonnet-4-6")

run_model_log "gpt-5.5" "openai" "$LOG_DIR/gpt.log" &
API_PIDS+=($!); API_NAMES+=("gpt-5.5")

# ── Ollama sequencial (foreground) ─────────────────────────────────────
echo "▶ Rodando Ollama sequencial (VRAM)..."
echo ""

run_model_log "qwen2.5-coder:7b" "ollama" "$LOG_DIR/qwen.log"
echo "  ✓ qwen2.5-coder:7b concluído"

run_model_log "deepseek-r1:7b" "ollama" "$LOG_DIR/deepseek.log"
echo "  ✓ deepseek-r1:7b concluído"

# ── Aguardar APIs ───────────────────────────────────────────────────────
echo ""
echo "▶ Aguardando APIs terminarem..."
FAIL=0
for i in "${!API_PIDS[@]}"; do
    pid="${API_PIDS[$i]}"
    name="${API_NAMES[$i]}"
    wait "$pid" && echo "  ✓ $name" || { echo "  ✗ $name"; FAIL=$((FAIL+1)); }
done

# ── Resultado ───────────────────────────────────────────────────────────
echo ""
echo "════════════════════════════════════════"
echo "  CONCLUÍDO. Falhas de API: $FAIL"
echo "  Logs: $LOG_DIR/"
echo "  JSONs: $ROOT/$OUT_DIR/"
echo "════════════════════════════════════════"
echo ""
echo "Ver resumo:"
echo "  python3 scripts/compare_benchmarks.py --dir $OUT_DIR"
