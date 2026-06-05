# V1 Evaluation Dataset

This dataset is intentionally controlled, but no longer only a happy-path smoke test. It is designed to evaluate the V1 claim: LLM findings can be materialized into executable verification obligations for ESBMC's Python frontend.

## Layout

- `ok/bugs/division_by_zero/`: 15 unsafe arithmetic denominator cases.
- `ok/bugs/out_of_bounds/`: 15 unsafe list-indexing cases.
- `ok/bugs/assertion_violation/`: 15 assertion-violation cases.
- `ok/clean/`: 10 guarded negative controls.
- `ok/smells/long_method/`: 5 local smell microbenchmarks.
- `ok/smells/many_parameters/`: 5 local smell microbenchmarks.
- `ok/smells/complex_conditional/`: 5 local smell microbenchmarks.
- `ground_truths/`: JSON annotations consumed by `research_pipeline.evaluator`.

## Design Rules

- Functions are library-style: no top-level calls.
- Parameters use simple type hints (`int`, `bool`, `list[int]`).
- Bug cases include obvious bugs, partial guards, off-by-one mistakes, branch-sensitive assertions, and guarded clean controls.
- Smell cases are heuristic maintainability cases and must not go to ESBMC in V1.
- No external modules, classes, I/O, async, or dynamic Python features.
- V1 metrics should use the formal ESBMC path only.

## Why This Dataset Exists

ESBMC's Python frontend verifies reachable executable code. Library-style functions without top-level calls can produce `Generated 0 VCC(s)` under direct ESBMC execution. The hybrid pipeline should improve on that baseline by using LLM findings to generate symbolic verification scenarios.

## Suggested Commands

```bash
python scripts/verify_benchmark_dataset.py dataset/labeled/ground_truths

python src/main.py --mode benchmark \
  --input dataset/labeled/ground_truths \
  --model gpt-5.5-2026-04-23 \
  --bound 5 \
  --timeout 30 \
  --report reports/json/benchmarks/benchmark_gpt-5.5.json

python scripts/run_benchmark_matrix.py \
  --models gpt-5.5-2026-04-23 claude qwen2.5-coder:7b \
  --ground-truth dataset/labeled/ground_truths \
  --bound 5 \
  --timeout 30 \
  --output-dir reports/json/benchmarks
```

See `docs/benchmarking.md` for the full repeatable flow and frontend instructions.
