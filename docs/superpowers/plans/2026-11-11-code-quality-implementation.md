# Code quality implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans. Execute the approved audit roadmap task by task and retain verification in the ledger.

**Goal:** Implement the maintenance roadmap in `docs/audits/code_quality_review.md`, fixing reproduced defects and reducing coupling without changing scientific policy.

**Architecture:** Keep existing data and verification contracts. Add a narrow OS execution boundary, shared process handling and pure CLI configuration/persistence helpers; extract only already distinct responsibilities.

**Tech Stack:** Python 3.11+, pytest, Ruff, Mypy, Linux Landlock via the standard library; existing ESBMC.

**Spec:** `docs/audits/code_quality_review.md`, especially sections 8–10, and the user's authorization to implement it.

## Global Constraints

- Work in the current checkout/branch and retain the local diff in Changes, as most recently requested.
- Do not change prompts, probes, datasets, ground truth, experimental results, tags, pricing, telemetry or token/context optimization.
- Preserve the other AI's commits, including `6c91ba2` and `ade6f14`.
- No live LLM calls; tests use fake providers and local executables.
- No deletions or historical moves without evidence; provide an index for conditional cleanup items.
- The later request to review Changes takes precedence over the earlier push request. Keep changes uncommitted for review; no force push.
- Preserve JSON, source maps and verdict rules. Record deliberate error/default/availability changes.

## Review Focus

- Unsupported OS isolation: untrusted execution must become explicitly unavailable, never run unconfined.
- Partial ESBMC output and descendants holding pipes: preserve evidence while terminating the command tree.
- Detection empty versus malformed response: persist failure and make resume retry it.
- CLI models/timeouts/flags: preserve explicit choices and propagate the whole configuration.
- Refactor compatibility: existing import/monkeypatch surfaces, fingerprints and serialized outputs must remain stable.

## Verification

Use `.venv/bin/python -m pytest` with default `not live_llm`, offline guards, temporary caches and no bytecode. Capture complete suite before/after; run targeted suites for each behavior change. New failure-path regressions must fail before the fix. Pure moves use existing behavioral tests and before/after artifacts. Run Ruff and Mypy with explicit committed policies. Review the complete diff once before commit/push.

### Task 1: Confine CPython execution (Q01)

**Files:** `verify/sandbox.py`, new `verify/confinement.py`, replay/differential workers, `verify/pytest_gen.py`, security tests.
**Interfaces:** `confine_writes(directory: Path) -> None`; raise `IsolationUnavailable` before loading untrusted code if unavailable. Worker startup communicates availability through its existing result/error paths.
- [x] RED: rejected aliased dangerous imports, getattr frame access, rebound self; real external sentinel write denied (including truncate/rename) and local result writing allowed; real-module import side effect denied; unsupported confinement produces unavailable.
- [x] GREEN: common unsafe-name policy, instance-only self dict exception, Landlock restriction before untrusted execution, generated pytest confinement.
- [x] Verify: security/replay/differential/pytest-generator suites, then relevant local ESBMC integration.

### Task 2: Reliable final-run shell (Q02)

**Files:** `scripts/run_final.sh`, new `tests/test_run_final.py`.
**Interfaces:** same CLI and output paths; nonzero exit on every failed stage; done only after success.
- [x] RED: fake executable fails each of five stages; no later stage/done; successful run and existing-output resume.
- [x] GREEN: explicit stage failure propagation, preserving existing operational sequence.
- [x] Verify: shell integration tests use only temporary copies/fake commands.

### Task 3: Preserve malformed-response errors (Q03)

**Files:** `llm/backends/chat_completions.py`, findings validation, `scan/pipeline.py`, backend/scan tests.
**Interfaces:** `analyze` returns findings only for a valid response; malformed/empty envelope raises a diagnostic exception; scan checkpoints retain error and resume retries failures.
- [x] RED: malformed JSON/shape/envelope distinguished from valid empty findings through real parsing and persisted scan state.
- [x] GREEN: explicit parse contract and failed-detection resume handling; retain telemetry implementation unchanged.
- [x] Verify: backend, scan and CLI detection suites offline.

### Task 4: Portable execution and isolated test environment (Q08/Q11)

**Files:** `maintenance/execution.py`, `verify/esbmc_knowledge.py` consumers/tests, `tests/conftest.py`, dev requirements and project configuration.
**Interfaces:** select an existing project interpreter or the active `sys.executable`; do not silently schedule an impossible command. Tests isolate caches and block accidental live calls.
- [x] RED: worker starts from a checkout without `.venv`; explicit missing interpreter diagnostic; cache writing stays under tmp_path.
- [x] GREEN: shared interpreter selection; tmp cache fixtures; declared Ruff/Mypy versions and Python floor.
- [x] Verify: maintenance/backend suites plus current-checkout baseline/collection.

### Task 5: Process lifecycle and agent deadlines (Q04/Q05)

**Files:** `verify/procs.py`, `verification/esbmc_runner.py`, `verify/agent_arm.py`, `verify/llm_client.py`, CLI wiring and process/agent tests.
**Interfaces:** shared command execution preserves partial stdout/stderr on timeout; existing `run_group` keeps its public result convention. API agent accepts the whole ESBMC command, ESBMC timeout and LLM timeout; each call is bounded by remaining total time.
- [x] RED: child in another session is gone after timeout; partial violation survives; slow fake LLM/ESBMC cannot return DONE after deadline; configured flags/timeouts reach operations.
- [x] GREEN: shared process primitive, bounded per-call timeout, compatibility for string ESBMC arguments and injected clients.
- [x] Verify: process, diagnose, runner, agent and CLI suites.

### Task 6: Pure backend/model resolution (Q06)

**Files:** new `research_pipeline/cli_config.py`, `src/main.py`, parameterized resolver/CLI tests.
**Interfaces:** `resolve_models(backend, model, synth_backend, synth_model)` preserves explicit synth model and CLI empty default; different API synth backend receives its own default.
- [x] RED: literal matrix for same/different backend, aliases, omitted/explicit models and CLI backends.
- [x] GREEN: one resolver shared by scan/hybrid, preserving existing input aliases and metadata keys.
- [x] Verify: configuration and CLI tests.

### Task 7: Extract CLI arguments and persistence (Q07)

**Files:** `src/main.py`, new CLI argument/persistence modules, scan's JSON writer and existing CLI/checkpoint tests.
**Interfaces:** keep `main.build_parser`, `_save_checkpoint` and existing entrypoint functions importable; byte-equivalent JSON and atomic replace.
- [x] Characterize: CLI defaults/help and saved checkpoint bytes before moving code.
- [x] Refactor: move argument construction and common atomic storage behind preserved imports/wrappers; leave telemetry/tokens and scientific orchestration unchanged.
- [x] Verify: same arguments, fingerprints, failure/resume behavior and JSON bytes.

### Task 8: Separate attempt preparation/evaluation from orchestration

**Files:** `verify/loop.py`, `verify/agent_arm.py`, new focused helper modules where justified, existing verify/agent tests.
**Interfaces:** retain `verify_hypothesis`, `run_agent_arm`, `evaluate_harness` and public result objects; retain source spans and verdict logic.
- [x] Characterize: representative confirmed, rejected, unavailable and retry result dictionaries.
- [x] Refactor: extract existing preparation/evaluation responsibilities with compatibility wrappers; no new policies or trial strategies.
- [x] Verify: engine/agent/healing/oracle and local integration suites.

### Task 9: Contracts and local dependency cycles (Q09)

**Files:** checkpoint/callable types, `verify/agent_scan.py`, shared source helpers used by agent/differential/pytest generation.
**Interfaces:** TypedDict/callable metadata expresses current JSON; helper extraction removes private agent imports without changing emitted source.
- [x] RED/characterize: parsing contract and metadata consumer behavior; literal source extraction expectations.
- [x] Refactor: narrow shared types and source helpers; incremental Mypy scope, without blanket ignores.
- [x] Verify: typed module checks and source/agent/differential/scan suites.

### Task 10: Small clones, comments and selected lint (Q10)

**Files:** `maintenance/execution.py`, `preprocess.py`, inspected comments, unused test import, committed Ruff policy.
- [x] Refactor duplicate gate callbacks and sync/async visitors only where behavior is identical; update obsolete operational comments.
- [x] Verify existing gate/preprocessor regressions; Ruff excludes ESBMC probes and scientific fixtures. Do not autoformat the repository.

### Task 11: Operational docs and conservative inventory

**Files:** README/TUTORIAL, new maintenance index, audit implementation status.
- [x] Correct Python/tool/ESBMC prerequisites and backend availability against code.
- [x] Index current versus historical material and script purposes; retain conditional/uncertain artifacts in place.
- [x] Run final offline suite, focused lint/types, immutable-content comparison and fresh whole-change review; fix material findings, leave the reviewed, uncommitted changes in the current checkout.

## Execution record

The per-task ledger is retained under `.superpowers/sdd/2026-11-11-code-quality-implementation/progress.md`. The approval is the user's instruction to implement the existing audit plan; no extra design approval or automatic historical deletion is inferred. Significant implementation decisions and test evidence go in the ledger and final implementation status.

Completed verification: `make lint typecheck` passes (Ruff; Mypy on nine
configured source modules), and the complete offline suite passes with 1,837
passed and 1 skipped. A process-concurrency regression reproduced a race in
the Linux subreaper cleanup; command-tree execution is now serialized and lock
wait counts against the operation timeout. Changes remain local and uncommitted
for review.
