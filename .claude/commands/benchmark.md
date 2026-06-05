# Benchmark V1 — comandos oficiais

## Um modelo

```bash
python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-4.1-nano \
  --bound 5 \
  --timeout 30 \
  --report reports/json/v1_benchmark/benchmark_gpt_4_1_nano.json
```

## Matriz de modelos

```bash
python3 scripts/run_benchmark_matrix.py \
  --models gpt-4.1-nano claude-sonnet qwen2.5-coder:7b \
  --ground-truth dataset/labeled/ground_truths \
  --output-dir reports/json/v1_benchmark \
  --bound 5 \
  --timeout 30
```

## Comparar JSONs

```bash
python3 scripts/compare_benchmarks.py --dir reports/json/v1_benchmark
```

## Visualizar no frontend

Abra `frontend/index.html` e arraste todos os arquivos:

```text
reports/json/v1_benchmark/benchmark_*.json
```

Use a aba **Benchmark / Modelos**.

## Validar dataset e ESBMC

```bash
python3 scripts/verify_dataset.py
python3 scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths
python3 scripts/run_esbmc_dataset.py
```
