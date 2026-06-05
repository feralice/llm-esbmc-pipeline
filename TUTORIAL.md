# Tutorial — Benchmark V1

Este guia roda a V1 pelo entry point oficial: `src/main.py --mode benchmark`.

## Pre-requisitos

```bash
cd /mnt/c/Users/ferna/Documents/mestrado/llm_esbmc
source .env
which esbmc
esbmc --version
```

## Rodar um modelo

```bash
python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4.1-nano \
  --bound 5 \
  --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt_4_1_nano.json
```

## Rodar matriz de modelos

```bash
python3 scripts/run_benchmark_matrix.py \
  --models gpt-4.1-nano claude-sonnet qwen2.5-coder:7b \
  --ground-truth dataset/labeled/ground_truths \
  --output-dir reports/json/v1_benchmark \
  --bound 5 \
  --timeout 30
```

Cada modelo gera um arquivo `benchmark_<modelo>.json` em `reports/json/v1_benchmark/`.

## Comparar resultados

```bash
python3 scripts/compare_benchmarks.py --dir reports/json/v1_benchmark
```

## Visualizar no frontend

Abra `frontend/index.html` no navegador. Na área **Benchmark / métricas**, selecione ou arraste todos os arquivos:

```text
reports/json/v1_benchmark/benchmark_*.json
```

Depois clique em **Carregar e visualizar** e use a aba **Benchmark / Modelos**.

## Validar dataset sem LLM

```bash
python3 scripts/verify_dataset.py
python3 scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths
python3 scripts/run_esbmc_dataset.py
```

## Testes

```bash
python3 -m pytest
```
