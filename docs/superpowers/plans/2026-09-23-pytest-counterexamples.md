# Pytest Counterexample Generation Implementation Plan

> **Status (2026-09-27): concluído.** A opção opt-in, persistência de
> metadados, tratamento não fatal, documentação e smoke test real foram
> implementados. Evidência: testes focados e suíte completa passando; o
> gerador do ESBMC também foi validado com um harness real.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Integrate ESBMC's `--generate-pytest-testcase` output into the V2 harness flow and document the feature in the presentation.

**Architecture:** After each generated harness is written, optionally run ESBMC's Pytest test-generation mode against that harness. Store the generated test path and generation status in the case result/report without changing the existing verification classification. Keep the feature opt-in to preserve current runs and avoid changing benchmark numbers unexpectedly.

**Tech Stack:** Python standard library, argparse, pytest, ESBMC 8.5, Markdown.

**Spec:** `https://esbmc.github.io/docs/python/pytest-testgen/`

## Global Constraints

- Do not send ground-truth data to the LLM or ESBMC.
- Do not change existing TP/FP/FN or confirmation semantics.
- Do not overwrite user-created Pytest files; use an explicit output directory.
- Keep default pipeline behavior unchanged unless the new option is enabled.

## Review Focus

- ESBMC unavailable or too old: report generation failure without losing the verification result.
- Generated file path: record the actual output path and do not assume the current directory.
- Harnesses without nondeterministic inputs: treat “no test generated” as an explicit status, not as a verification failure.
- Pytest generation command failure: preserve the original ESBMC classification.
- Resume/report serialization: generated-test metadata must round-trip safely.

### Task 1: Add the opt-in generation interface

**Files:**
- Modify: `src/main.py`
- Test: `tests/test_main_v2.py`

- [ ] Add a V2 CLI option for enabling Pytest counterexample generation and an output directory option.
- [ ] Write a parser test proving the defaults are disabled and the explicit options parse.
- [ ] Pass the options into `run_pipeline_scan`.

### Task 2: Run ESBMC Pytest generation and persist metadata

**Files:**
- Modify: `src/research_pipeline/scan/pipeline.py`
- Modify: `src/research_pipeline/scan/synth.py` only if command helper reuse is needed
- Test: `tests/test_scan_pipeline.py`

- [ ] Write a failing test showing that an enabled run invokes ESBMC with `--generate-pytest-testcase` and records the generated path.
- [ ] Write a failing test showing that generation failure leaves the original classification unchanged.
- [ ] Implement a small helper that runs ESBMC generation with `--pytest-output-dir` in a per-case directory.
- [ ] Add nullable metadata fields to `ScanCaseResult` and its serialization.
- [ ] Call the helper after the harness has been written and the normal verification result is available.
- [ ] Keep generation opt-in and non-fatal.

### Task 3: Update documentation and presentation

**Files:**
- Modify: `README.md` or `TUTORIAL.md`
- Modify: `docs/projeto/complemento_apresentacao_2026-09-23.md`

- [ ] Document the command and the generated `pytest` artifact.
- [ ] State that ESBMC produces concrete tests from symbolic inputs/counterexamples; this is separate from LLM harness generation.
- [ ] Update the “mudanças desde 09/09” slide to say the feature is available.

### Task 4: Verify

- [ ] Run the focused parser and pipeline tests.
- [ ] Run the full test suite with `python3 -m pytest -q`.
- [ ] Run one real ESBMC smoke command with the new option and inspect the generated Pytest file.
