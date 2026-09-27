# Pipeline Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task.

## Goal

Improve the pipeline's detection quality, auditability, retry transparency, and resumability without changing the current default behavior: `single` remains the default strategy, `two_stage` remains opt-in, and no category-specific few-shot mechanism is introduced.

## Architecture

- Keep detection, synthesis, verification, telemetry, checkpointing, and reporting as separate layers.
- Treat every LLM attempt as an independently auditable event.
- Preserve the existing scalar and real-body harness paths.
- Add stage-aware metadata for `single`, `localize`, `classify`, and synthesis calls.
- Never reuse an old ESBMC/Pytest verdict as evidence for a changed harness.

## Tech Stack

- Python application code under `src/research_pipeline/` and `src/main.py`.
- Pytest tests under `tests/`.
- JSON reports/checkpoints and Markdown documentation under `docs/`.
- Existing LLM telemetry helpers and provider adapters; no new runtime dependency.

## Specification

`docs/superpowers/specs/2026-09-27-pipeline-improvements-design.md`

## Global Constraints

- Do not add category-specific few-shots.
- Do not change the default `single` strategy or silently switch strategies.
- Do not mix `single` and `two_stage` results in one evaluation baseline.
- Do not add live LLM calls to the default test suite.
- Preserve backward compatibility when reading older reports/checkpoints.
- Keep failures explicit; do not turn missing or invalid measurements into normal successful results.

## Review Focus

- Telemetry counts must not double-count a staged call.
- Detection reports must distinguish located, classified, rejected, and failed findings.
- Retry history must identify the attempt, failure layer, and whether a new harness was verified.
- Resume must not duplicate candidates, events, or results.
- Tests must cover both `single` and `two_stage` paths, including partial/failure cases.

## Tasks

### Task 1: Make staged detection telemetry complete and stage-aware

Files:

- Modify `src/research_pipeline/llm/staged.py`.
- Modify the provider adapters in `src/research_pipeline/llm/backends/` that implement `analyze_stage`.
- Extend `tests/test_llm_staged.py` and `tests/test_main_v2.py`.

Implementation:

1. Ensure each staged provider call emits exactly one response telemetry event with provider, model, status, duration, token usage when available, and `analysis_stage` set to `localize` or `classify`.
2. Keep parser/validation failures attached to the same stage event instead of producing an unclassified duplicate event.
3. Preserve the existing failure behavior: a localization failure returns no candidates for that unit; a classification failure remains explicit and is not converted into a valid classification.
4. Extend aggregate telemetry with stage call counts and token totals without changing existing fields.

Tests:

- A successful staged run has one event per provider call and correct stage labels.
- A classification failure is counted once and remains visible.
- Existing `single` telemetry remains unchanged.

### Task 2: Add a structured detection trace to V2 reports

Files:

- Modify `src/research_pipeline/llm/staged.py`.
- Modify `src/main.py`.
- Extend `tests/test_main_v2.py` and `tests/test_llm_staged.py`.

Implementation:

1. Record per-unit detection trace data: unit/function identifier, strategy, localization candidate count, classification count, rejected count, and failure stage/error when applicable.
2. Include aggregate counts in the V2 detection section: located candidates, classified candidates, classification rejections, localization failures, and stage-specific calls.
3. Keep the trace independent of ground-truth labels and compatible with old reports that have no trace.
4. Ensure `single` reports remain valid and use `single` as their explicit strategy value.

Tests:

- A mixed successful/failed scan produces the expected trace and aggregate counts.
- A `single` scan does not invent localize/classify calls.
- Loading a legacy report without the new fields still works.

### Task 3: Make retry attempts fully auditable

Files:

- Modify `src/research_pipeline/scan/pipeline.py`.
- Extend `tests/test_pipeline_reliability.py`.

Implementation:

1. Populate `attempt_history` for every synthesis/verification attempt, including attempt number, failure layer, compatibility result, ESBMC/Pytest status, token/time usage, and final outcome.
2. Preserve valid harness text as repair context where appropriate, but never carry forward ESBMC/Pytest verdicts, assumptions, or summaries as if they belonged to the new harness.
3. Keep retry behavior backward-compatible for existing callers and older serialized results.
4. Make the final error identify the last failed layer and retain the earlier attempt records.

Tests:

- A compatibility failure followed by a successful repair records both attempts.
- A verification failure followed by a successful repair records distinct verification results.
- Deserialization of older results without `attempt_history` remains valid.

### Task 4: Harden checkpoint/resume observability

Files:

- Inspect and modify `src/main.py` and `src/research_pipeline/scan/pipeline.py` only where needed.
- Extend `tests/test_pipeline_reliability.py` and `tests/test_main_v2.py`.

Implementation:

1. Preserve the fingerprint inputs for strategy, prompts, source content, and synthesis configuration.
2. Record resume statistics for reused, skipped, retried, and newly processed units.
3. Ensure resumed runs do not duplicate detection traces, telemetry events, candidates, or final results.
4. Keep checkpoint writes atomic and backward-compatible.

Tests:

- Running the same scan twice with a checkpoint reuses prior work without duplicate output.
- Changing detection strategy or prompt inputs invalidates the checkpoint.
- A partially failed checkpoint resumes only the incomplete work.

### Task 5: Improve evaluation/reporting for detection quality

Files:

- Modify `src/main.py` and, if required by existing interfaces, `src/research_pipeline/v2_evaluator.py`.
- Extend relevant V2 evaluator/report tests.
- Update `docs/v2/two_stage_detection.md`.

Implementation:

1. Report detection metrics separately from harness/verification metrics.
2. Preserve real-body versus scalar evaluation dimensions.
3. Report per-category and per-strategy results only when measured; do not fabricate metrics from absent data.
4. Keep the two-stage experiment isolated from the default baseline and document how to compare raw reports.

Tests:

- Missing measurements remain distinguishable from measured zero.
- Real-body/scalar metrics remain separate.
- Strategy-specific reports cannot silently merge into one baseline.

### Task 6: Documentation and final verification

Files:

- Update the relevant pipeline README/tutorial/report documentation.
- Add concise operator guidance for interpreting `single`, `two_stage`, retry history, and detection traces.

Validation commands:

```bash
pytest -q
pytest -q tests/test_llm_staged.py tests/test_main_v2.py tests/test_pipeline_reliability.py
git diff --check
```

Completion criteria:

- The full test suite passes.
- The focused pipeline tests pass.
- Reports expose the new observability fields without breaking old inputs.
- No category-specific few-shot code or documentation is added.
