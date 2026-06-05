# Benchmark V1

This is the repeatable V1 flow for comparing multiple LLMs on the Python ESBMC pipeline.

## What V1 Measures

V1 has three groups:

- Bugs formally checked by ESBMC after LLM + AST validation and `--function` execution:
  - `division_by_zero`
  - `out_of_bounds`
  - `assertion_violation`
- Clean negative controls, expected to produce no findings.
- Heuristic smells, expected to be detected by the LLM only:
  - `long_method`
  - `many_parameters`
  - `complex_conditional`

Smells are not sent to ESBMC in V1 because they are maintainability findings, not runtime safety properties.

## Validate Dataset

Run this before a benchmark run:

```bash
.venv/bin/python3 -m compileall -q dataset/labeled/ok
.venv/bin/python3 scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths
```

Expected shape after the V1 seed dataset:

```text
cases: 70
assertion_violation: 15
clean: 10
complex_conditional: 5
division_by_zero: 15
long_method: 5
many_parameters: 5
out_of_bounds: 15
```

## Run One Model

```bash
.venv/bin/python3 src/main.py \
  --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-5.5-2026-04-23 \
  --bound 5 \
  --timeout 30 \
  --report reports/json/benchmarks/benchmark_gpt-5.5.json
```

## Run Several Models

```bash
.venv/bin/python3 scripts/run_benchmark_matrix.py \
  --models gpt-5.5-2026-04-23 claude qwen2.5-coder:7b \
  --ground-truth dataset/labeled/ground_truths \
  --bound 5 \
  --timeout 30 \
  --output-dir reports/json/benchmarks
```

The runner writes one JSON per model plus:

```text
reports/json/benchmarks/benchmark_matrix_manifest.json
```

## Frontend

Open:

```text
frontend/index.html
```

Use the Benchmark / Modelos tab and load the generated `benchmark_*.json` files. The frontend supports comparing multiple model reports and exporting CSV.

For quick manual notes while comparing GPT, Claude and Ollama, open:

```text
frontend/benchmark_notes.html
```

Load multiple `full_report.json`, `report.json` or benchmark JSON files, mark a manual verdict, add notes, and export CSV/JSON annotations.

## Important V1 Choice

The V1 claim is specifically:

LLM finding -> AST validation -> ESBMC `--function` -> ESBMC confirmation.

Flow A is the ESBMC-only baseline: the AST lists candidate functions and ESBMC runs each one with `--function`, without LLM findings or category hints. Flow B is LLM+ESBMC with `--function`. Flow C is LLM-only and makes no ESBMC calls.

## External Smell Dataset Note

The public SmellyCodeDataset contains Python smell examples and is MIT licensed. If examples are copied verbatim, keep source attribution and license text in the repo. The current V1 smell cases are local microbenchmarks adapted to this pipeline style, not verbatim copies.
