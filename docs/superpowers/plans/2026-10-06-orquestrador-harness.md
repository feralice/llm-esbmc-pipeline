# Orquestrador de harness: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** tirar mais vereditos dos casos travados no nível 1, escolhendo o braço pelo motivo do travamento, com uma busca no CPython como braço barato.

**Architecture:** o executor do CPython (`replay_worker.py`) ganha uma passada aleatória; `verify/dynamic.py` roda essa busca no programa já gerado de um resultado travado; `verify/routing.py` decide a sequência de braços pelo veredito e motivo; `verify/orchestrator.py` aplica a sequência com retomada; `scripts/v2_orchestrate.py` roda tudo sobre um relatório pronto, nos 20 casos difíceis.

**Tech Stack:** Python 3.12, pytest, ESBMC 8.5.0, Claude Code CLI (agente), `LLMClient` (agente via API).

**Spec:** `docs/superpowers/specs/2026-10-06-orquestrador-harness-design.md`

## Global Constraints

- Nenhuma regra escrita para um bug específico do dataset; padrões de motivo são classes gerais.
- `FUZZ_FOUND` nunca vira CONFIRMED nem soma com ele; métrica principal: bugs do gabarito confirmados na linha.
- Modelo pago só com confirmação dela; padrão do agente via API é `claude_cli` (assinatura).
- Sem dependência nova (nada de Hypothesis).
- Medição nos 20 casos de `dataset/bugs_reais/conjunto_dificil.json`, reaproveitando o relatório `full-2026-10-05-regrounded`; rodada completa só no fim, se houver ganho.
- Nunca usar `--no-unwinding-assertions`.
- Textos para ela sem travessão.

## Review Focus

1. Programa com `assume` que rejeita toda entrada: a busca aleatória precisa terminar no orçamento e dar `FUZZ_NOTHING`, não travar.
2. Resultado travado sem `program_path` (GROUNDING_FAILED, aninhado): `FUZZ_UNAVAILABLE`, sem exceção.
3. Motivo que não casa com nenhum padrão: rota padrão (dinâmico), nunca exceção.
4. Retomada depois de interrupção: braços já rodados não rodam de novo.
5. Um braço que levanta exceção não derruba a rodada: vira `ARM_FAILED` na linha daquele caso.

---

### Tarefa 1: passada aleatória no executor do CPython

**Files:**
- Modify: `src/research_pipeline/verify/replay_worker.py`
- Modify: `src/research_pipeline/verify/replay.py` (`concrete_replay`)
- Test: `tests/test_verify_replay_random.py`

**Interfaces:**
- Produces: `concrete_replay(program, function, *, max_runs=400, timeout_seconds=20, seeds=None, seeds_only=False, random_runs=0, seed=0) -> ReplayVerdict`

- [ ] **Passo 1: teste que falha**

```python
from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import concrete_replay

NEEDS_BIG = (
    "def f(x: int) -> int:\n"
    "    if x > 50:\n"
    "        return 1 // 0\n"
    "    return x\n"
    "\n"
    "f(nondet_int())\n"
)
NEEDS_SPACE = (
    "def g(s: str) -> str:\n"
    "    if ' ' in s:\n"
    "        return [][0]\n"
    "    return s\n"
    "\n"
    "g(nondet_str())\n"
)
NEVER = (
    "def h(x: int) -> int:\n"
    "    return 1 // 0\n"
    "\n"
    "x = nondet_int()\n"
    "__ESBMC_assume(x != x)\n"
    "h(x)\n"
)


def test_the_exhaustive_pass_alone_misses_a_large_value() -> None:
    program = Program(NEEDS_BIG, 0, ((3, 3),), (), (1, 4))
    assert concrete_replay(program, "f").status == "not_reproduced"


def test_the_random_pass_reaches_a_large_int_and_a_string_with_a_space() -> None:
    big = concrete_replay(Program(NEEDS_BIG, 0, ((3, 3),), (), (1, 4)), "f", random_runs=300, seed=1)
    space = concrete_replay(Program(NEEDS_SPACE, 0, ((3, 3),), (), (1, 4)), "g", random_runs=300, seed=1)
    assert big.status == "reproduced" and big.line == 3
    assert space.status == "reproduced" and space.exception_type == "IndexError"


def test_an_assume_that_rejects_everything_ends_without_a_crash() -> None:
    verdict = concrete_replay(Program(NEVER, 0, ((2, 2),), (), (1, 2)), "h", random_runs=300, seed=1)
    assert verdict.status == "not_reproduced"
```

- [ ] **Passo 2:** `python3 -m pytest tests/test_verify_replay_random.py -q`
  Expected: o primeiro passa; os outros falham com `TypeError: concrete_replay() got an unexpected keyword argument 'random_runs'`.

- [ ] **Passo 3: implementação no worker**

Em `replay_worker.py`, depois de `MAX_LIST = 2`:

```python
RANDOM_MAX_LIST = 5


class _RandomChooser:
    def __init__(self, rng):
        self.rng = rng
        self.sizes = []

    def pick(self, domain):
        self.sizes.append(len(domain))
        return self.rng.choice(domain)


def _random_domains(rng):
    """Wider values than DOMAINS: edges and sampled ints, strings with separators and non-ASCII."""
    edges = [0, 1, -1, 2, -2, 3, 7, 10, 100, 127, 128, 255, 256, 1000, -1000, 2**31 - 1, -2**31, 2**63 - 1]
    return {
        int: edges + [rng.randint(-10**6, 10**6) for _ in range(30)],
        float: [0.0, -0.0, 0.5, -1.5, 1.0, -1.0, 1e9, -1e-9, 3.14, float("inf"), float("-inf"), float("nan")],
        bool: [False, True],
        str: ["", "a", " ", "0", "-1", "1.5", "abc", "a b", "a.b", "a,b", "a/b", "a\\b", "\n", "\t", "é",
              "%s", "{}", "'", '"', " x ", "A" * 40, "None", "true"],
    }
```

`_intrinsics(chooser, domains=None, max_list=MAX_LIST)`: trocar os dois `MAX_LIST` de `nondet_list` por `max_list`.

Em `main`, depois de montar `passes`, e o laço de cada passada passa a aceitar um escolhedor aleatório:

```python
    if config.get("random_runs") and not config.get("seeds_only"):
        rng = random.Random(config.get("seed", 0))
        passes.append((_random_domains(rng), config["random_runs"], rng))
    for domains, budget, *random_pass in passes:
        vector, used = [], 0
        while vector is not None and used < budget and time.monotonic() < deadline:
            chooser = _RandomChooser(random_pass[0]) if random_pass else _Chooser(vector)
            ...  # corpo atual, com _intrinsics(chooser, domains, RANDOM_MAX_LIST if random_pass else MAX_LIST)
            vector = [] if random_pass else _next_vector(vector, chooser.sizes)
```

(`import random` no topo.) As passadas existentes continuam como tuplas de dois itens.

- [ ] **Passo 4: implementação em `concrete_replay`**

Assinatura ganha `random_runs: int = 0, seed: int = 0`; o `config` ganha `"random_runs": random_runs, "seed": seed`.

- [ ] **Passo 5:** `python3 -m pytest tests/test_verify_replay_random.py tests/ -q -k "replay"`
  Expected: todos passam.

- [ ] **Passo 6: commit**

```bash
git add src/research_pipeline/verify/replay_worker.py src/research_pipeline/verify/replay.py tests/test_verify_replay_random.py
git commit -m "Add a seeded random pass to the CPython replay search"
```

---

### Tarefa 2: braço dinâmico sobre um resultado travado

**Files:**
- Create: `src/research_pipeline/verify/dynamic.py`
- Modify: `src/research_pipeline/verify/validation.py` (tornar público `_replay_program` como `replay_program_path`)
- Test: `tests/test_verify_dynamic.py`

**Interfaces:**
- Consumes: `concrete_replay(..., random_runs, seed)`; `program_for_result(path, hypothesis)`; `replay_program_path(result) -> Path | None`
- Produces: `FUZZ_FOUND, FUZZ_OTHER, FUZZ_NOTHING, FUZZ_UNAVAILABLE`; `dynamic_check(result: dict, *, random_runs: int = 300, timeout_seconds: int = 60, seed: int = 0) -> dict` com chaves `verdict`, `reason`, `replay`.

- [ ] **Passo 1: teste que falha**

```python
from pathlib import Path

from research_pipeline.verify.dynamic import FUZZ_FOUND, FUZZ_NOTHING, FUZZ_UNAVAILABLE, dynamic_check

PROGRAM = (
    "def f(x: int) -> int:\n"
    "    return 10 // (x - 100)\n"
    "\n"
    "f(nondet_int())\n"
)


def _result(tmp_path: Path, source: str | None, verdict: str = "UNSUPPORTED") -> dict:
    hypothesis = {"function": "f", "suspect_expression": "10 // (x - 100)", "hypothesis_id": "h"}
    if source is None:
        return {"hypothesis": hypothesis, "verdict": "GROUNDING_FAILED", "attempts": []}
    path = tmp_path / "h_a0.py"
    path.write_text(source)
    return {"hypothesis": hypothesis, "verdict": verdict, "program_path": str(path), "attempts": [{}]}


def test_a_crash_at_the_hypothesis_line_is_fuzz_found(tmp_path: Path) -> None:
    outcome = dynamic_check(_result(tmp_path, PROGRAM), seed=1)
    assert outcome["verdict"] == FUZZ_FOUND and outcome["replay"]["exception_type"] == "ZeroDivisionError"


def test_nothing_found_in_the_budget(tmp_path: Path) -> None:
    safe = PROGRAM.replace("10 // (x - 100)", "10 // (abs(x) + 1)")
    result = _result(tmp_path, safe)
    result["hypothesis"]["suspect_expression"] = "10 // (abs(x) + 1)"
    assert dynamic_check(result, seed=1)["verdict"] == FUZZ_NOTHING


def test_no_program_is_unavailable(tmp_path: Path) -> None:
    assert dynamic_check(_result(tmp_path, None))["verdict"] == FUZZ_UNAVAILABLE
```

- [ ] **Passo 2:** `python3 -m pytest tests/test_verify_dynamic.py -q` → Expected: erro de import (`No module named ...dynamic`).

- [ ] **Passo 3: implementação**

Em `validation.py`, renomear `_replay_program` para `replay_program_path` (e o uso em `_validate_row`).

`src/research_pipeline/verify/dynamic.py`:

```python
"""Dynamic arm: search the generated program under CPython when ESBMC gave no verdict.

Evidence only: a crash found here is never a formal confirmation."""

from __future__ import annotations

from pathlib import Path

from .replay import concrete_replay
from .validation import program_for_result, replay_program_path

FUZZ_FOUND = "FUZZ_FOUND"
FUZZ_OTHER = "FUZZ_OTHER"
FUZZ_NOTHING = "FUZZ_NOTHING"
FUZZ_UNAVAILABLE = "FUZZ_UNAVAILABLE"

_BY_STATUS = {"reproduced": FUZZ_FOUND, "other_failure": FUZZ_OTHER, "not_reproduced": FUZZ_NOTHING}


def dynamic_check(result: dict, *, random_runs: int = 300, timeout_seconds: int = 60, seed: int = 0) -> dict:
    if not result.get("program_path"):
        return {"verdict": FUZZ_UNAVAILABLE, "reason": "no generated program", "replay": {}}
    path = replay_program_path(result)
    program = None if path is None else program_for_result(path, result["hypothesis"])
    if program is None:
        return {"verdict": FUZZ_UNAVAILABLE, "reason": "hypothesis not found in the pre-rewrite program", "replay": {}}
    replay = concrete_replay(program, result["hypothesis"]["function"].split(".")[-1], random_runs=random_runs,
                             timeout_seconds=timeout_seconds, seed=seed)
    return {"verdict": _BY_STATUS.get(replay.status, FUZZ_UNAVAILABLE), "reason": replay.reason,
            "replay": replay.to_dict()}
```

- [ ] **Passo 4:** `python3 -m pytest tests/test_verify_dynamic.py tests/test_verify_validation.py -q` → Expected: todos passam.

- [ ] **Passo 5: commit**

```bash
git add src/research_pipeline/verify/dynamic.py src/research_pipeline/verify/validation.py tests/test_verify_dynamic.py
git commit -m "Search a stuck result's program under CPython as a dynamic arm"
```

---

### Tarefa 3: rota pelo motivo do travamento

**Files:**
- Create: `src/research_pipeline/verify/routing.py`
- Test: `tests/test_verify_routing.py`

**Interfaces:**
- Produces: `DYNAMIC = "dynamic"`, `API_AGENT = "api_agent"`, `CLAUDE_AGENT = "claude_agent"`; `route(result: dict) -> tuple[str, ...]`; `limit_class(result: dict) -> str`.

- [ ] **Passo 1: teste que falha** (motivos reais da rodada `full-2026-10-05-regrounded`)

```python
import pytest

from research_pipeline.verify.routing import API_AGENT, CLAUDE_AGENT, DYNAMIC, route


def _r(verdict: str, reason: str = "") -> dict:
    return {"verdict": verdict, "reason": reason}


@pytest.mark.parametrize(("verdict", "reason", "expected"), [
    ("MISSING_DEPENDENCY", "ERROR: Module 'layers' not found.", (CLAUDE_AGENT, DYNAMIC)),
    ("MISSING_DEPENDENCY", 'ERROR: Function "opfunc" not found', (CLAUDE_AGENT, DYNAMIC)),
    ("MISSING_DEPENDENCY", "ERROR: Base class not found: MutableMapping", (CLAUDE_AGENT, DYNAMIC)),
    ("SPEC_FAILED", "", (API_AGENT, CLAUDE_AGENT, DYNAMIC)),
    ("UNVALIDATED", "", (API_AGENT, CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "TypeError: __init__() takes 1 positional argument but 2 were given",
     (API_AGENT, CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "ERROR: Unsupported expression Starred at line 26", (DYNAMIC,)),
    ("UNSUPPORTED", "ERROR: unsupported: non-constant argument in str % formatting", (DYNAMIC,)),
    ("UNSUPPORTED", "external call Substitution(...) uses *args/**kwargs", (DYNAMIC,)),
    ("UNSUPPORTED", "ERROR: uncaught exception [16irep2_cast_error]: irep2", (DYNAMIC,)),
    ("GROUNDING_FAILED", "function 'rnn._step' not found (or ambiguous)", (DYNAMIC,)),
    ("ESBMC_TIMEOUT", "ESBMC direto excedeu o tempo limite de 180s.", (DYNAMIC,)),
    ("ESBMC_ERROR", "ESBMC direto: resultado inconclusivo.", (DYNAMIC,)),
    ("CONFIRMED", "", ()),
    ("NOT_CONFIRMED", "", ()),
    ("ESBMC_MISSED", "", ()),
    ("UNSUPPORTED", "something never seen before", (DYNAMIC,)),
])
def test_route(verdict, reason, expected) -> None:
    assert route(_r(verdict, reason)) == expected
```

- [ ] **Passo 2:** `python3 -m pytest tests/test_verify_routing.py -q` → Expected: erro de import.

- [ ] **Passo 3: implementação**

```python
"""Which arms to try after the deterministic harness, by why it stopped. Rules are classes of
reasons, never cases of the dataset."""

from __future__ import annotations

import re

DYNAMIC = "dynamic"
API_AGENT = "api_agent"
CLAUDE_AGENT = "claude_agent"

_DONE = {"CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED"}
# Context outside the function: an agent that can open the project may supply it.
_CONTEXT = re.compile(r"not found|undefined name", re.I)
# The harness itself was wrong: rewriting it is enough.
_HARNESS = re.compile(r"TypeError: .*(?:positional argument|unexpected keyword|missing \d+ required)", re.I)

_ROUTES = {
    "done": (),
    "context": (CLAUDE_AGENT, DYNAMIC),
    "harness": (API_AGENT, CLAUDE_AGENT, DYNAMIC),
    "esbmc_limit": (DYNAMIC,),
}


def limit_class(result: dict) -> str:
    verdict, reason = result["verdict"], result.get("reason", "")
    if verdict in _DONE:
        return "done"
    if verdict in {"SPEC_FAILED", "UNVALIDATED"} or _HARNESS.search(reason):
        return "harness"
    if verdict == "MISSING_DEPENDENCY" or (verdict == "UNSUPPORTED" and _CONTEXT.search(reason)):
        return "context"
    return "esbmc_limit"


def route(result: dict) -> tuple[str, ...]:
    return _ROUTES[limit_class(result)]
```

- [ ] **Passo 4:** `python3 -m pytest tests/test_verify_routing.py -q` → Expected: 17 passam.

- [ ] **Passo 5: commit**

```bash
git add src/research_pipeline/verify/routing.py tests/test_verify_routing.py
git commit -m "Route a stuck result to harness arms by why it stopped"
```

---

### Tarefa 4: orquestrador com retomada

**Files:**
- Create: `src/research_pipeline/verify/orchestrator.py`
- Test: `tests/test_verify_orchestrator.py`

**Interfaces:**
- Consumes: `route(result)`; braços como `Callable[[dict], dict]` que devolvem ao menos `{"verdict": ...}`.
- Produces: `ARM_FAILED = "ARM_FAILED"`; `orchestrate(results, *, arms, state, save, route=route) -> list[dict]`; cada linha: `{"hypothesis_id", "engine_verdict", "route", "steps": [{"arm", "verdict", ...}], "final": <verdict>}`.

- [ ] **Passo 1: teste que falha**

```python
from research_pipeline.verify.orchestrator import ARM_FAILED, orchestrate


def _r(hid: str, verdict: str, reason: str = "") -> dict:
    return {"hypothesis": {"hypothesis_id": hid}, "verdict": verdict, "reason": reason}


def _run(results, arms, state=None):
    state = {} if state is None else state
    return orchestrate(results, arms=arms, state=state, save=lambda: None), state


def test_a_formal_verdict_stops_the_sequence_and_fuzz_found_does_not() -> None:
    calls = []
    arms = {"api_agent": lambda r: calls.append("api") or {"verdict": "UNSUPPORTED"},
            "claude_agent": lambda r: calls.append("claude") or {"verdict": "CONFIRMED"},
            "dynamic": lambda r: calls.append("dyn") or {"verdict": "FUZZ_FOUND"}}
    rows, _ = _run([_r("a", "SPEC_FAILED")], arms)
    assert calls == ["api", "claude"] and rows[0]["final"] == "CONFIRMED"


def test_done_results_run_no_arm_and_missing_arms_are_skipped() -> None:
    rows, _ = _run([_r("a", "CONFIRMED"), _r("b", "MISSING_DEPENDENCY")], {"dynamic": lambda r: {"verdict": "FUZZ_NOTHING"}})
    assert rows[0]["steps"] == [] and rows[0]["final"] == "CONFIRMED"
    assert [s["arm"] for s in rows[1]["steps"]] == ["dynamic"] and rows[1]["final"] == "FUZZ_NOTHING"


def test_an_arm_that_raises_is_recorded_and_the_next_one_runs() -> None:
    def broken(_):
        raise RuntimeError("boom")
    rows, _ = _run([_r("a", "SPEC_FAILED")], {"api_agent": broken, "dynamic": lambda r: {"verdict": "FUZZ_NOTHING"}})
    assert rows[0]["steps"][0]["verdict"] == ARM_FAILED and rows[0]["final"] == "FUZZ_NOTHING"


def test_resume_skips_finished_cases() -> None:
    calls = []
    arms = {"dynamic": lambda r: calls.append(1) or {"verdict": "FUZZ_NOTHING"}}
    _, state = _run([_r("a", "ESBMC_TIMEOUT")], arms)
    _run([_r("a", "ESBMC_TIMEOUT")], arms, state)
    assert calls == [1]
```

- [ ] **Passo 2:** `python3 -m pytest tests/test_verify_orchestrator.py -q` → Expected: erro de import.

- [ ] **Passo 3: implementação**

```python
"""Try the arms ``route`` picks for each result, cheapest first; a formal verdict ends the sequence."""

from __future__ import annotations

from typing import Callable

from .routing import route as default_route

ARM_FAILED = "ARM_FAILED"
_FORMAL = {"CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED"}


def orchestrate(results: list[dict], *, arms: dict[str, Callable[[dict], dict]], state: dict,
                save: Callable[[], None], route=default_route) -> list[dict]:
    done = state.setdefault("orchestrated", {})
    for result in results:
        key = result["hypothesis"]["hypothesis_id"]
        if key in done:
            continue
        planned = route(result)
        row = {"hypothesis_id": key, "engine_verdict": result["verdict"], "route": list(planned), "steps": [],
               "final": result["verdict"]}
        for arm in planned:
            if arm not in arms:
                continue
            try:
                outcome = arms[arm](result)
            except Exception as exc:  # noqa: BLE001 - one broken arm must not end the run
                outcome = {"verdict": ARM_FAILED, "reason": f"{type(exc).__name__}: {exc}"}
            row["steps"].append({"arm": arm, **outcome})
            if outcome["verdict"] != ARM_FAILED:
                row["final"] = outcome["verdict"]
            if outcome["verdict"] in _FORMAL:
                break
        done[key] = row
        save()
    wanted = {r["hypothesis"]["hypothesis_id"] for r in results}
    return [row for key, row in done.items() if key in wanted]
```

Nota: uma linha que termina num braço sem veredito formal fica com o veredito do último braço que respondeu; `FUZZ_FOUND` de um braço anterior continua visível em `steps`.

- [ ] **Passo 4:** `python3 -m pytest tests/test_verify_orchestrator.py -q` → Expected: 4 passam.

- [ ] **Passo 5: commit**

```bash
git add src/research_pipeline/verify/orchestrator.py tests/test_verify_orchestrator.py
git commit -m "Orchestrate harness arms per stuck result with resume"
```

---

### Tarefa 5: script sobre um relatório pronto

**Files:**
- Create: `scripts/v2_orchestrate.py`
- Modify: `src/research_pipeline/v2_evaluator.py` (mover `at_bug_line` de `scripts/v2_hard_set.py` para cá; o script passa a importar)
- Test: `tests/test_v2_orchestrate.py`

**Interfaces:**
- Consumes: `orchestrate`, `dynamic_check`, `run_agent_arm`, `make_agent`, `verification_source`, `at_bug_line`.
- Produces: `scripts/v2_orchestrate.py <report> --only <ids> --arms dynamic,api_agent,claude_agent --out <dir>`; grava `<dir>/orchestrated.json` com `config`, `rows` e `summary` (`final` por veredito; `confirmed_at_bug`; `fuzz_found_at_bug`).

- [ ] **Passo 1: teste que falha** (só o resumo, sem ESBMC nem LLM)

```python
import importlib.util
from pathlib import Path

_SPEC = importlib.util.spec_from_file_location(
    "v2_orchestrate", Path(__file__).resolve().parents[1] / "scripts" / "v2_orchestrate.py")
v2_orchestrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2_orchestrate)

GT = {"a": {"function": "f", "expression": "x[i]", "crash_expressions": []}}


def _result(hid, expression):
    return {"hypothesis": {"hypothesis_id": hid, "file": "d/a.py", "function": "f", "suspect_expression": expression}}


def test_summary_counts_formal_and_dynamic_findings_at_the_bug_line_apart() -> None:
    results = [_result("1", "x[i]"), _result("2", "x[i]"), _result("3", "y")]
    rows = [{"hypothesis_id": "1", "final": "CONFIRMED", "steps": []},
            {"hypothesis_id": "2", "final": "FUZZ_FOUND", "steps": []},
            {"hypothesis_id": "3", "final": "CONFIRMED", "steps": []}]
    summary = v2_orchestrate.summarize(rows, results, GT)
    assert summary["confirmed_at_bug"] == 1 and summary["fuzz_found_at_bug"] == 1
    assert summary["final"] == {"CONFIRMED": 2, "FUZZ_FOUND": 1}
```

- [ ] **Passo 2:** `python3 -m pytest tests/test_v2_orchestrate.py -q` → Expected: `FileNotFoundError` do script.

- [ ] **Passo 3: implementação**

Mover `at_bug_line` para `v2_evaluator.py` (mesmo corpo); em `scripts/v2_hard_set.py`, `from research_pipeline.v2_evaluator import at_bug_line, expressions_equivalent` e apagar a cópia local. Rodar `tests/test_v2_hard_set.py` de novo.

`scripts/v2_orchestrate.py`:

```python
"""Run the harness orchestrator on a finished verify report (no detection LLM call).

  python scripts/v2_orchestrate.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json \
      --only "$(jq -r .ids dataset/bugs_reais/conjunto_dificil.json)" --arms dynamic --out artifacts/v2/orq-...
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import at_bug_line  # noqa: E402
from research_pipeline.verify.agent_arm import make_agent, run_agent_arm  # noqa: E402
from research_pipeline.verify.dynamic import FUZZ_FOUND, dynamic_check  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402
from research_pipeline.verify.loop import verification_source  # noqa: E402
from research_pipeline.verify.orchestrator import orchestrate  # noqa: E402


def summarize(rows: list[dict], results: list[dict], ground_truth: dict) -> dict:
    by_id = {r["hypothesis"]["hypothesis_id"]: r["hypothesis"] for r in results}

    def at_bug(row):
        h = by_id[row["hypothesis_id"]]
        item = ground_truth.get(Path(h["file"]).stem)
        return item is not None and at_bug_line(h, item)

    return {"final": dict(Counter(r["final"] for r in rows)),
            "confirmed_at_bug": sum(r["final"] == "CONFIRMED" and at_bug(r) for r in rows),
            "fuzz_found_at_bug": sum(r["final"] == FUZZ_FOUND and at_bug(r) for r in rows)}


def _agent_arm(backend, args):
    agent, skill = make_agent(backend, model=args.agent_model, esbmc=args.esbmc, bound=args.bound)
    sources = Path(args.verification_sources)

    def run(result):
        h = BugHypothesis(**{k: v for k, v in result["hypothesis"].items() if k != "hypothesis_id"})
        return run_agent_arm(h, work_dir=Path(args.out) / f"{backend}_cases", run_agent=agent,
                             esbmc_command=[args.esbmc], bound=args.bound, timeout_seconds=args.timeout,
                             agent_timeout=args.agent_timeout, source_path=verification_source(h, sources),
                             skill=skill)
    return run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("report")
    parser.add_argument("--only", default="", help="comma-separated hypothesis ids")
    parser.add_argument("--arms", default="dynamic", help="subset of dynamic,api_agent,claude_agent")
    parser.add_argument("--api-backend", default="claude_cli", help="LLMClient backend of the API agent")
    parser.add_argument("--agent-model", default=None)
    parser.add_argument("--verification-sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--agent-timeout", type=int, default=900)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    wanted = set(filter(None, args.only.split(",")))
    results = [r for r in results if not wanted or r["hypothesis"]["hypothesis_id"] in wanted]
    builders = {"dynamic": lambda: dynamic_check,
                "api_agent": lambda: _agent_arm(args.api_backend, args),
                "claude_agent": lambda: _agent_arm("claude", args)}
    arms = {name: builders[name]() for name in args.arms.split(",")}
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    state_path = out / "orchestrator_state.json"
    config = {"report": args.report, "arms": sorted(arms), "api_backend": args.api_backend,
              "agent_model": args.agent_model, "bound": args.bound, "timeout": args.timeout}
    state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {}
    if state.get("config") != config:
        state = {"config": config}
    rows = orchestrate(results, arms=arms, state=state,
                       save=lambda: state_path.write_text(json.dumps(state, indent=2), encoding="utf-8"))
    items = {i["id"]: i for i in json.loads(Path(args.ground_truth).read_text(encoding="utf-8"))["items"]}
    summary = summarize(rows, results, items)
    (out / "orchestrated.json").write_text(json.dumps({"config": config, "rows": rows, "summary": summary},
                                                      indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Passo 4:** `python3 -m pytest tests/test_v2_orchestrate.py tests/test_v2_hard_set.py -q` → Expected: todos passam.

- [ ] **Passo 5:** suíte inteira: `timeout 590 python3 -m pytest tests/ -q` → Expected: tudo verde.

- [ ] **Passo 6: commit**

```bash
git add scripts/v2_orchestrate.py scripts/v2_hard_set.py src/research_pipeline/v2_evaluator.py tests/test_v2_orchestrate.py
git commit -m "Run the harness orchestrator on a finished report"
```

---

### Tarefa 6: medições e registro

Sem código novo; cada rodada registrada em `docs/experimentos/README.md` (fase 9) e arquivada com `scripts/archive_runs.py`.

- [ ] **Passo 1: estimativa sem rodar nada.** Aplicar `limit_class` a todos os resultados de `full-2026-10-05-regrounded` e contar por classe (quantos casos cada braço receberia). Registrar.
- [ ] **Passo 2: dinâmico nos 20.** `scripts/v2_orchestrate.py ... --only <ids> --arms dynamic --out artifacts/v2/orq-2026-10-0X-dyn-20`. Expected: termina em minutos; registrar `fuzz_found_at_bug`.
- [ ] **Passo 3: dinâmico em todos os travados** (sem `--only`) e o **controle** em `control-fixed-2026-10-06/report_0of1.json`. `FUZZ_FOUND` na linha do bug na versão corrigida conta como falso alarme.
- [ ] **Passo 4: agentes nos 20.** `--arms dynamic,api_agent,claude_agent` (API por `claude_cli`). Comparar com o passo 2: quanto os agentes acrescentam em `confirmed_at_bug`.
- [ ] **Passo 5:** se houver ganho, registrar a decisão de levar `--orchestrate` ao `main.py` num plano à parte; se não, registrar o resultado negativo.
