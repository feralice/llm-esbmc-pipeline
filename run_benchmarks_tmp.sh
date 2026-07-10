#!/bin/bash
set -e
PROJECT="/mnt/c/Users/ferna/Documents/mestrado/llm_esbmc"
cd "$PROJECT"
set -a; source .env; set +a
source .venv/bin/activate
echo "Python: $(python --version)"
echo "Start: $(date)"
echo "[1/3] DeepSeek R1 7B"
python -m src.main --mode benchmark --backend ollama --model deepseek-r1:7b --input dataset/labeled/ground_truths --output-dir output/v2/deepseek-r1-7b --report reports/json/v1_benchmark/benchmark_deepseek-r1-7b.json
echo "[1/3] DeepSeek DONE $(date)"
echo "[2/3] Qwen2.5-Coder 7B"
python -m src.main --mode benchmark --backend ollama --model qwen2.5-coder:7b --input dataset/labeled/ground_truths --output-dir output/v2/qwen2.5-coder-7b --report reports/json/v1_benchmark/benchmark_qwen2.5-coder-7b.json
echo "[2/3] Qwen DONE $(date)"
echo "[3/3] Gemini 3.1 Flash-Lite"
python -m src.main --mode benchmark --backend google --model gemini-3.1-flash-lite --input dataset/labeled/ground_truths --output-dir output/v2/gemini-3.1-flash-lite --report reports/json/v1_benchmark/benchmark_gemini-3.1-flash-lite.json
echo "[3/3] Gemini DONE $(date)"
echo "ALL BENCHMARKS COMPLETE $(date)"