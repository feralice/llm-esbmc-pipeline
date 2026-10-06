# Validação dos vereditos e melhoria da detecção: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** saber se os vereditos do pipeline V2 são confiáveis (preservação, vacuidade, mutação) e medir, uma mudança por vez, o que faz a LLM achar mais bugs.

**Architecture:** um módulo novo `verify/validation.py` reavalia rodadas já feitas, sem LLM (só ESBMC e CPython), e um script `scripts/v2_validate.py` o executa sobre uma pasta de rodada. Na detecção, variantes do prompt V2 viram transformações nomeadas (`llm/prompt_variants.py`) escolhidas por `--v2-variants`, e um estágio `--v2-stage detection` para depois da detecção, para medir cada variante sem gastar verificação.

**Tech Stack:** Python 3.12, `ast`, `subprocess`, pytest; ESBMC 8.5.0 em `/usr/local/bin/esbmc`; LLM via `claude_cli` (assinatura).

**Spec:** `docs/superpowers/specs/2026-10-06-validacao-e-deteccao-design.md`

## Global Constraints

- Nada roda antes de terminar a rodada `artifacts/v2/agent-2026-10-06-e2e` (cota e memória).
- Trabalhar direto no `master` deste repositório (preferência da Fernanda, sobrepõe a regra global de branch).
- **Commit só com autorização explícita da Fernanda**, sem `Co-Authored-By`, mensagem em inglês no estilo do repo (título imperativo < 72 caracteres, corpo de 2 a 4 linhas).
- Arquivos com quebra de linha CRLF (ex.: `src/research_pipeline/verification/esbmc_runner.py`): editar preservando os bytes `\r\n`; conferir com `git diff --stat` que só as linhas novas mudaram.
- ESBMC: `/usr/local/bin/esbmc` 8.5.0. Checagem de alcance sempre com `--enable-unreachability-intrinsic`; **proibido** `--no-unwinding-assertions` junto com ela.
- Exemplos e textos de prompt nunca tirados do dataset; nenhuma variante vê gabarito, patch ou arquivo corrigido.
- Toda rodada nova entra em `docs/experimentos/README.md` e é arquivada com `python scripts/archive_runs.py <pasta> --fase 9`.
- Suíte: `python3 -m pytest tests/ -q` (cerca de 7 minutos; limite de 10). Comentários raros, só o porquê.
- Sem travessão (—) em nenhum texto.

## Review Focus

1. Hipótese numa condição de `elif`: inserir `__ESBMC_unreachable()` antes dela quebra a sintaxe; a checagem tem que dar `inconclusive`, nunca exceção (teste na Tarefa 4).
2. Resultado sem programa (`GROUNDING_FAILED`, `SPEC_FAILED`): a validação pula sem erro e conta como "sem programa" (teste na Tarefa 8).
3. ESBMC que trava ou ignora `SIGTERM` durante a checagem de alcance: o grupo inteiro morre no limite e o resultado é `inconclusive` (teste na Tarefa 1, reaproveitado na 4).
4. Prompt V2 editado e uma variante não acha mais o trecho que troca: tem que falhar alto (`ValueError` com o nome da variante), não virar a linha de base em silêncio (teste na Tarefa 10).
5. Retomar com outras variantes: `--resume` precisa recusar, porque a variante entra na configuração que forma a impressão digital (teste na Tarefa 10).

---

### Tarefa 1: processos do agente morrem juntos no tempo esgotado (parte 0)

**Files:**
- Create: `src/research_pipeline/verify/procs.py`
- Modify: `src/research_pipeline/verify/agent_arm.py:79-80`
- Test: `tests/test_verify_procs.py`

**Interfaces:**
- Produces: `run_group(command: list[str], *, timeout_seconds: int, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess | None` (None = tempo esgotado, grupo morto com `SIGKILL`).

- [ ] **Passo 1: teste que falha**

```python
# tests/test_verify_procs.py
import os
import time
from pathlib import Path

from research_pipeline.verify.procs import run_group


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_timeout_kills_the_grandchildren_too(tmp_path: Path) -> None:
    pidfile = tmp_path / "child.pid"
    script = tmp_path / "spawn.sh"
    # The grandchild ignores SIGTERM, like ESBMC stuck in the solver.
    script.write_text(f"#!/bin/sh\nsh -c 'trap \"\" TERM; sleep 300' &\necho $! > {pidfile}\nsleep 300\n")
    script.chmod(0o755)

    assert run_group([str(script)], timeout_seconds=2) is None

    time.sleep(0.5)
    assert not _alive(int(pidfile.read_text()))


def test_a_finished_command_returns_its_output(tmp_path: Path) -> None:
    done = run_group(["sh", "-c", "echo ok"], timeout_seconds=10)
    assert done is not None and done.stdout.strip() == "ok"
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_procs.py -q`
Expected: FAIL com `ModuleNotFoundError: research_pipeline.verify.procs`

- [ ] **Passo 3: implementação mínima**

```python
# src/research_pipeline/verify/procs.py
"""Run a command in its own process group so a timeout also stops what it spawned."""

from __future__ import annotations

import os
import signal
import subprocess
from pathlib import Path


def run_group(command: list[str], *, timeout_seconds: int, cwd: Path | None = None,
              env: dict | None = None) -> subprocess.CompletedProcess | None:
    """None when the time runs out: the whole group gets SIGKILL (ESBMC can ignore SIGTERM in the solver)."""
    process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        return None
    return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
```

E em `agent_arm.claude_agent`, trocar as linhas 79-80:

```python
        completed = run_group(command, cwd=cwd, timeout_seconds=timeout_seconds, env=env)
        if completed is None:
            raise subprocess.TimeoutExpired(command, timeout_seconds)
```

com `from .procs import run_group` junto dos imports do módulo (quem chama já trata `TimeoutExpired`, linhas 195 e 213).

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_procs.py tests/ -q -k "procs or agent"`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/procs.py src/research_pipeline/verify/agent_arm.py tests/test_verify_procs.py
git commit -m "Kill the agent's whole process group when it runs out of time"
```

### Tarefa 2: assinatura do corpo e programa de um resultado, em um lugar só

**Files:**
- Modify: `src/research_pipeline/verify/astutil.py` (nova função `body_signature`)
- Modify: `src/research_pipeline/verify/agent_arm.py:145-150` (usar `body_signature`)
- Create: `src/research_pipeline/verify/validation.py` (com `program_for_result`, movida de `scripts/v2_reverdict.py:_program`)
- Modify: `scripts/v2_reverdict.py:30-39` (importar `program_for_result`)
- Test: `tests/test_verify_validation.py`

**Interfaces:**
- Produces: `body_signature(function: ast.FunctionDef) -> list[str]`; `program_for_result(path: Path, hypothesis: dict) -> Program | None`.

- [ ] **Passo 1: teste que falha**

```python
# tests/test_verify_validation.py
import ast
from pathlib import Path

from research_pipeline.verify.astutil import body_signature, find_function
from research_pipeline.verify.validation import program_for_result

SOURCE = 'def f(n):\n    """doc"""\n    return 10 // n\n'


def test_body_signature_ignores_the_docstring() -> None:
    without = find_function(ast.parse("def f(n):\n    return 10 // n\n"), "f")
    assert body_signature(find_function(ast.parse(SOURCE), "f")) == body_signature(without)


def test_program_for_result_marks_the_hypothesis_lines(tmp_path: Path) -> None:
    path = tmp_path / "p.py"
    path.write_text(SOURCE)
    program = program_for_result(path, {"function": "f", "suspect_expression": "10 // n"})
    assert program is not None and program.target_spans == ((3, 3),) and program.target_range == (1, 3)
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_validation.py -q`
Expected: FAIL com `ImportError: cannot import name 'body_signature'`

- [ ] **Passo 3: implementação**

Em `astutil.py`:

```python
def body_signature(function: ast.FunctionDef) -> list[str]:
    """The body without its docstring as AST dumps: equal signatures run the same code."""
    body = function.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
            and isinstance(body[0].value.value, str):
        body = body[1:]
    return [ast.dump(stmt, include_attributes=False) for stmt in body]
```

Em `agent_arm.py`, apagar `_body` (linhas 145-150), importar `body_signature` de `.astutil` e trocar os usos `_body(` por `body_signature(`.

Novo `validation.py`:

```python
"""Whether a verify verdict means what it says: the target is the original code (V1), a "safe"
verdict examined the hypothesis line (V2), and the harness catches faults injected near it (V3)."""

from __future__ import annotations

import ast
from pathlib import Path

from .astutil import expression_nodes, find_function
from .render import Program


def program_for_result(path: Path, hypothesis: dict) -> Program | None:
    source = path.read_text(encoding="utf-8")
    function = find_function(ast.parse(source), hypothesis["function"])
    if function is None:
        return None
    nodes = expression_nodes(function, hypothesis["suspect_expression"])
    if not nodes:
        return None
    spans = tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes}))
    return Program(source, 0, spans, (), (function.lineno, function.end_lineno))
```

Em `scripts/v2_reverdict.py`, apagar `_program` e usar `from research_pipeline.verify.validation import program_for_result` (mesma chamada, nome novo).

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_validation.py tests/ -q -k "validation or agent or reverdict"`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/astutil.py src/research_pipeline/verify/agent_arm.py src/research_pipeline/verify/validation.py scripts/v2_reverdict.py tests/test_verify_validation.py
git commit -m "Share the body signature and result program between checks"
```

### Tarefa 3: V1, preservação da função

**Files:**
- Modify: `src/research_pipeline/verify/validation.py`
- Test: `tests/test_verify_validation.py`

**Interfaces:**
- Consumes: `body_signature`, `find_function` (Tarefa 2).
- Produces: `target_preserved(original_source: str, program_source: str, function: str) -> bool`.

- [ ] **Passo 1: teste que falha**

```python
from research_pipeline.verify.validation import target_preserved

HARNESS = SOURCE + "\n\ndef driver():\n    f(nondet_int())\n"


def test_a_harness_around_the_unchanged_function_preserves_it() -> None:
    assert target_preserved(SOURCE, HARNESS, "f")


def test_a_simplified_body_is_not_preserved() -> None:
    assert not target_preserved(SOURCE, HARNESS.replace("10 // n", "10 // (n or 1)"), "f")


def test_a_missing_target_is_not_preserved() -> None:
    assert not target_preserved(SOURCE, "def driver():\n    pass\n", "f")
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_validation.py -q -k preserv`
Expected: FAIL com `ImportError: cannot import name 'target_preserved'`

- [ ] **Passo 3: implementação**

```python
from .astutil import body_signature, expression_nodes, find_function


def target_preserved(original_source: str, program_source: str, function: str) -> bool:
    original = find_function(ast.parse(original_source), function)
    checked = find_function(ast.parse(program_source), function)
    return original is not None and checked is not None and body_signature(original) == body_signature(checked)
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_validation.py -q`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/validation.py tests/test_verify_validation.py
git commit -m "Check that a verdict's program runs the original function"
```

### Tarefa 4: V2, alcance da linha da hipótese

**Files:**
- Modify: `src/research_pipeline/verify/validation.py`
- Test: `tests/test_verify_validation.py`, `tests/test_verify_esbmc_integration.py`

**Interfaces:**
- Consumes: `run_group` (Tarefa 1), `Program`.
- Produces: `REACHABLE, UNREACHABLE, INCONCLUSIVE` (str); `with_unreachable_marker(source: str, line: int) -> str | None`; `read_reachability(output: str | None) -> str`; `reachability(program: Program, *, esbmc: str, unwind: int, timeout_seconds: int, work_dir: Path) -> str`.

- [ ] **Passo 1: testes que falham (puros e com ESBMC real)**

```python
# tests/test_verify_validation.py
from research_pipeline.verify.validation import (INCONCLUSIVE, REACHABLE, UNREACHABLE,
                                                 read_reachability, with_unreachable_marker)

GUARDED = "def f(n):\n    if n > 10:\n        return 1 // (n - 11)\n    return 0\n"


def test_the_marker_goes_right_before_the_statement_of_the_line() -> None:
    marked = with_unreachable_marker(GUARDED, 3)
    assert marked.splitlines()[2] == "        __ESBMC_unreachable()"


def test_a_marker_that_would_break_an_elif_gives_none() -> None:
    source = "def f(n):\n    if n:\n        return 0\n    elif n > 1:\n        return 1\n    return 2\n"
    assert with_unreachable_marker(source, 4) is None


@pytest.mark.parametrize(("output", "expected"), [
    ("  FAILED [f.reachable-error.1] line 4 reachability: unreachable code reached\nVERIFICATION FAILED", REACHABLE),
    ("  PASSED [f.reachable-error.1] line 4 reachability: unreachable code reached\nVERIFICATION SUCCESSFUL", UNREACHABLE),
    ("  PASSED [f.reachable-error.1] line 4 reachability: unreachable code reached\n"
     "  FAILED [f.unwind.1] line 2 unwinding assertion loop 1\nVERIFICATION FAILED", INCONCLUSIVE),
    (None, INCONCLUSIVE),
    ("ERROR: Type inference failed", INCONCLUSIVE),
])
def test_read_reachability(output, expected) -> None:
    assert read_reachability(output) == expected
```

(adicionar `import pytest` no topo do arquivo de teste)

```python
# tests/test_verify_esbmc_integration.py (no fim; o arquivo já pula sem o ESBMC)
from research_pipeline.verify.render import Program
from research_pipeline.verify.validation import REACHABLE, UNREACHABLE, reachability

REACH = ("def f(n: int) -> int:\n    if n > 10:\n        return 1 // (n - 11)\n    return 0\n\n\n"
         "def driver() -> None:\n    n: int = nondet_int()\n    __ESBMC_assume(n < {limit})\n    f(n)\n\n\ndriver()\n")


@pytest.mark.parametrize(("limit", "expected"), [(5, UNREACHABLE), (50, REACHABLE)])
def test_reachability_of_the_hypothesis_line(tmp_path, limit, expected):
    program = Program(REACH.format(limit=limit), 0, ((3, 3),), (), (1, 4))
    assert reachability(program, esbmc=str(ESBMC), unwind=5, timeout_seconds=60, work_dir=tmp_path) == expected
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_validation.py tests/test_verify_esbmc_integration.py -q -k "reach or marker"`
Expected: FAIL com `ImportError`

- [ ] **Passo 3: implementação**

```python
from .procs import run_group

REACHABLE, UNREACHABLE, INCONCLUSIVE = "reachable", "unreachable", "inconclusive"
_REACH = "reachability: unreachable code reached"


def with_unreachable_marker(source: str, line: int) -> str | None:
    """The program with ``__ESBMC_unreachable()`` right before the statement holding ``line``."""
    covering = [n for n in ast.walk(ast.parse(source))
                if isinstance(n, ast.stmt) and n.lineno <= line <= (n.end_lineno or n.lineno)]
    if not covering:
        return None
    statement = max(covering, key=lambda n: (n.lineno, n.col_offset))
    lines = source.splitlines()
    lines.insert(statement.lineno - 1, " " * statement.col_offset + "__ESBMC_unreachable()")
    marked = "\n".join(lines) + "\n"
    try:
        ast.parse(marked)
    except SyntaxError:
        return None  # e.g. an elif condition: nothing can go between the branches
    return marked


def read_reachability(output: str | None) -> str:
    if output is None:
        return INCONCLUSIVE
    lines = output.splitlines()
    if any("FAILED" in line and _REACH in line for line in lines):
        return REACHABLE
    if any("FAILED" in line and "unwinding assertion" in line for line in lines):
        return INCONCLUSIVE  # a truncated loop proves nothing about reachability
    if any("PASSED" in line and _REACH in line for line in lines) or "VERIFICATION SUCCESSFUL" in output:
        return UNREACHABLE
    return INCONCLUSIVE


def reachability(program: Program, *, esbmc: str, unwind: int, timeout_seconds: int, work_dir: Path) -> str:
    if not program.target_spans:
        return INCONCLUSIVE
    marked = with_unreachable_marker(program.source, program.target_spans[0][0])
    if marked is None:
        return INCONCLUSIVE
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / "reach.py"
    path.write_text(marked, encoding="utf-8")
    done = run_group([esbmc, path.name, "--enable-unreachability-intrinsic", "--unwind", str(unwind),
                      "--multi-property"], timeout_seconds=timeout_seconds, cwd=work_dir)
    return read_reachability(None if done is None else done.stdout + done.stderr)
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_validation.py tests/test_verify_esbmc_integration.py -q -k "reach or marker"`
Expected: PASS (7 casos)

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/validation.py tests/test_verify_validation.py tests/test_verify_esbmc_integration.py
git commit -m "Check whether a safe verdict reached the hypothesis line"
```

### Tarefa 5: V3, matriz das mutações naturais (com bug e corrigida)

**Files:**
- Modify: `src/research_pipeline/verify/validation.py`
- Test: `tests/test_verify_validation.py`

**Interfaces:**
- Produces: `natural_mutation_matrix(buggy: list[dict], fixed: list[dict]) -> dict` com as chaves `only_buggy`, `both`, `only_fixed` (listas de `hypothesis_id`) e `neither` (int).

- [ ] **Passo 1: teste que falha**

```python
from research_pipeline.verify.validation import natural_mutation_matrix


def _r(hid: str, verdict: str) -> dict:
    return {"hypothesis": {"hypothesis_id": hid}, "verdict": verdict}


def test_natural_mutation_matrix_separates_real_bugs_from_false_alarms() -> None:
    buggy = [_r("a", "CONFIRMED"), _r("b", "CONFIRMED"), _r("c", "NOT_CONFIRMED"), _r("d", "UNSUPPORTED")]
    fixed = [_r("a", "NOT_CONFIRMED"), _r("b", "CONFIRMED"), _r("c", "CONFIRMED")]

    matrix = natural_mutation_matrix(buggy, fixed)

    assert matrix == {"only_buggy": ["a"], "both": ["b"], "only_fixed": ["c"], "neither": 1}
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_validation.py -q -k natural`
Expected: FAIL com `ImportError`

- [ ] **Passo 3: implementação**

```python
from .outcome import CONFIRMED


def natural_mutation_matrix(buggy: list[dict], fixed: list[dict]) -> dict:
    """Confirmed on the buggy version only: the bug. On both: a crash the fix did not touch (a false
    alarm for the reported bug, e.g. an input no caller passes)."""
    fixed_confirmed = {r["hypothesis"]["hypothesis_id"] for r in fixed if r["verdict"] == CONFIRMED}
    matrix: dict = {"only_buggy": [], "both": [], "only_fixed": [], "neither": 0}
    for result in buggy:
        hid = result["hypothesis"]["hypothesis_id"]
        on_buggy, on_fixed = result["verdict"] == CONFIRMED, hid in fixed_confirmed
        if on_buggy and on_fixed:
            matrix["both"].append(hid)
        elif on_buggy:
            matrix["only_buggy"].append(hid)
        elif on_fixed:
            matrix["only_fixed"].append(hid)
        else:
            matrix["neither"] += 1
    return matrix
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_validation.py -q -k natural`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/validation.py tests/test_verify_validation.py
git commit -m "Tabulate verdicts on the buggy and fixed versions"
```

### Tarefa 6: V3, operadores de mutação artificial

**Files:**
- Modify: `src/research_pipeline/verify/validation.py`
- Test: `tests/test_verify_validation.py`

**Interfaces:**
- Produces: `Mutant(operator: str, line: int, source: str)` (NamedTuple); `mutants(source: str, function: str, near_line: int, *, window: int = 5, per_operator: int = 2) -> list[Mutant]`. Os operadores mantêm a numeração das linhas (a linha trocada vira uma só, completada com linhas vazias).

- [ ] **Passo 1: teste que falha**

```python
from research_pipeline.verify.validation import mutants

TARGET = (
    "def f(xs, i, limit):\n"
    "    if xs is None:\n"
    "        return 0\n"
    "    v = xs[i]\n"
    "    total = limit\n"
    "    return v if i < len(xs) else total\n"
)


def test_each_operator_yields_a_mutant_that_keeps_the_line_numbers() -> None:
    found = {m.operator: m for m in mutants(TARGET, "f", near_line=4)}

    assert set(found) == {"remove_guard", "assign_none", "index_plus_one", "lt_to_le"}
    assert "if xs is None" not in found["remove_guard"].source
    assert "total = None" in found["assign_none"].source
    assert "xs[i + 1]" in found["index_plus_one"].source
    assert "i <= len(xs)" in found["lt_to_le"].source
    assert all(len(m.source.splitlines()) == len(TARGET.splitlines()) for m in found.values())


def test_no_mutant_far_from_the_hypothesis() -> None:
    assert mutants(TARGET, "f", near_line=40, window=2) == []
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_validation.py -q -k mutant`
Expected: FAIL com `ImportError`

- [ ] **Passo 3: implementação**

```python
import copy
from typing import NamedTuple


class Mutant(NamedTuple):
    operator: str
    line: int
    source: str


_SIMPLE = (ast.Assign, ast.AugAssign, ast.Expr, ast.Return)


def _replace(source: str, statement: ast.stmt, text: str) -> str:
    lines = source.splitlines()
    first, last = statement.lineno, statement.end_lineno or statement.lineno
    lines[first - 1:last] = [" " * statement.col_offset + text] + [""] * (last - first)
    return "\n".join(lines) + "\n"


def _mutated(statement: ast.stmt, change) -> str | None:
    copied = copy.deepcopy(statement)
    if not change(copied):
        return None
    return ast.unparse(copied).splitlines()[0] if isinstance(copied, _SIMPLE) else None


def _plus_one(statement: ast.stmt) -> bool:
    for node in ast.walk(statement):
        if isinstance(node, ast.Subscript) and not isinstance(node.slice, ast.Slice):
            node.slice = ast.BinOp(node.slice, ast.Add(), ast.Constant(1))
            return True
    return False


def _lt_to_le(statement: ast.stmt) -> bool:
    for node in ast.walk(statement):
        if isinstance(node, ast.Compare) and any(isinstance(op, ast.Lt) for op in node.ops):
            node.ops = [ast.LtE() if isinstance(op, ast.Lt) else op for op in node.ops]
            return True
    return False


def mutants(source: str, function: str, near_line: int, *, window: int = 5, per_operator: int = 2) -> list[Mutant]:
    """Faults that raise when reached, injected near the hypothesis: they show whether the harness
    exercises that code. Line numbers do not move."""
    target = find_function(ast.parse(source), function)
    if target is None:
        return []
    found: list[Mutant] = []
    counts: dict[str, int] = {}

    def add(operator: str, statement: ast.stmt, text: str | None) -> None:
        if text is None or counts.get(operator, 0) >= per_operator:
            return
        counts[operator] = counts.get(operator, 0) + 1
        found.append(Mutant(operator, statement.lineno, _replace(source, statement, text)))

    for statement in ast.walk(target):
        if not isinstance(statement, ast.stmt) or statement is target or abs(statement.lineno - near_line) > window:
            continue
        if (isinstance(statement, ast.If) and not statement.orelse and len(statement.body) == 1
                and isinstance(statement.body[0], (ast.Return, ast.Raise))):
            add("remove_guard", statement, "pass")
        if isinstance(statement, ast.Assign) and len(statement.targets) == 1 \
                and isinstance(statement.targets[0], ast.Name):
            add("assign_none", statement, f"{statement.targets[0].id} = None")
        if isinstance(statement, _SIMPLE):
            add("index_plus_one", statement, _mutated(statement, _plus_one))
            add("lt_to_le", statement, _mutated(statement, _lt_to_le))
    return found
```

Nota: `assign_none` em `total = limit` gera `total = None`, que quebra quando `total` é usado; em `v = xs[i]` gera `v = None`, que pode nem quebrar. Por isso a Tarefa 7 descarta mutantes que o CPython não consegue quebrar.

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_validation.py -q -k mutant`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/validation.py tests/test_verify_validation.py
git commit -m "Generate line-preserving faults near a hypothesis"
```

### Tarefa 7: V3, executar um mutante (morto, sobrevivente ou não conta)

**Files:**
- Modify: `src/research_pipeline/verify/validation.py`
- Test: `tests/test_verify_esbmc_integration.py`

**Interfaces:**
- Consumes: `Mutant` (Tarefa 6); `check`, `esbmc_output` de `.esbmc_run`; `concrete_replay`, `counterexample_seeds` de `.replay`.
- Produces: `KILLED, SURVIVED, NOT_COUNTED` (str); `run_mutant(mutant: Mutant, function: str, target_range: tuple[int, int], *, esbmc_command: list[str], bound: int, timeout_seconds: int, work_dir: Path) -> str`.

- [ ] **Passo 1: teste que falha (ESBMC real)**

```python
from research_pipeline.verify.validation import KILLED, NOT_COUNTED, Mutant, run_mutant

DRIVEN = ("def f(xs: list[int], i: int) -> int:\n    if i >= len(xs):\n        return 0\n    return xs[i]\n\n\n"
          "def driver() -> None:\n    xs: list[int] = [nondet_int(), nondet_int()]\n    i: int = nondet_int()\n"
          "    __ESBMC_assume(i >= 0)\n    f(xs, i)\n\n\ndriver()\n")


def test_removing_the_bound_guard_is_killed(tmp_path):
    mutant = Mutant("remove_guard", 2, DRIVEN.replace("    if i >= len(xs):\n        return 0\n", "    pass\n\n"))
    assert run_mutant(mutant, "f", (1, 4), esbmc_command=[str(ESBMC)], bound=5, timeout_seconds=60,
                      work_dir=tmp_path) == KILLED


def test_a_mutant_no_input_breaks_does_not_count(tmp_path):
    mutant = Mutant("assign_none", 4, DRIVEN.replace("return xs[i]", "return len(xs)"))
    assert run_mutant(mutant, "f", (1, 4), esbmc_command=[str(ESBMC)], bound=5, timeout_seconds=60,
                      work_dir=tmp_path) == NOT_COUNTED
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_esbmc_integration.py -q -k mutant`
Expected: FAIL com `ImportError`

- [ ] **Passo 3: implementação**

```python
from .esbmc_run import check, esbmc_output
from .replay import concrete_replay, counterexample_seeds

KILLED, SURVIVED, NOT_COUNTED = "killed", "survived", "not_counted"


def run_mutant(mutant: Mutant, function: str, target_range: tuple[int, int], *, esbmc_command: list[str],
               bound: int, timeout_seconds: int, work_dir: Path) -> str:
    """Killed: ESBMC reports a violation and CPython raises. Survived: CPython raises, ESBMC says safe.
    Not counted: no input made CPython raise (equivalent mutant or out of the search)."""
    work_dir.mkdir(parents=True, exist_ok=True)
    path = work_dir / f"mutant_{mutant.operator}_{mutant.line}.py"
    path.write_text(mutant.source, encoding="utf-8")
    result, reading, _ = check(path, esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                               work_dir=work_dir / path.stem)
    program = Program(mutant.source, 0, ((mutant.line, mutant.line),), (), target_range)
    replay = concrete_replay(program, function.split(".")[-1], seeds=counterexample_seeds(esbmc_output(result), None))
    if replay.status not in {"reproduced", "other_failure"}:
        return NOT_COUNTED
    return KILLED if reading.kind == "violation" else SURVIVED
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_esbmc_integration.py -q -k mutant`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/research_pipeline/verify/validation.py tests/test_verify_esbmc_integration.py
git commit -m "Run an injected fault through ESBMC and the CPython replay"
```

### Tarefa 8: validar uma rodada inteira (`scripts/v2_validate.py`)

**Files:**
- Modify: `src/research_pipeline/verify/validation.py` (função `validate_results`)
- Create: `scripts/v2_validate.py`
- Test: `tests/test_verify_validation.py`

**Interfaces:**
- Consumes: Tarefas 2 a 7.
- Produces: `validate_results(results: list[dict], *, sources: Path, esbmc: str, timeout_seconds: int, work_dir: Path, control: list[dict] | None = None, with_mutants: bool = False, reach=reachability, run=run_mutant) -> dict` com `rows` (uma por resultado), `summary` e, se houver controle, `natural_mutation`.

Regras de cada linha:
- sem `program_path`: `{"checked": False}`;
- `preserved`: `target_preserved(original, programa de reexecução ou programa, função)`; original = `sources/<nome do arquivo>` se existir, senão o arquivo da hipótese;
- `reachability`: só para `NOT_CONFIRMED`, `ESBMC_MISSED` e `CONFIRMED`, com o `unwind` da última tentativa (padrão 5);
- `validated_verdict`: `TARGET_ALTERED` se não preservada; `NOT_CONFIRMED_VACUOUS` se `NOT_CONFIRMED` e inalcançável; senão o veredito original;
- `mutants` (com `with_mutants`): contagem `killed/survived/not_counted` nos resultados com veredito do ESBMC.

- [ ] **Passo 1: teste que falha (sem ESBMC: injeta `reach` e `run` falsos)**

```python
from research_pipeline.verify.validation import validate_results


def test_validate_results_reclassifies_and_skips_results_without_program(tmp_path: Path) -> None:
    src = tmp_path / "src"; src.mkdir()
    (src / "a.py").write_text(SOURCE)
    program = tmp_path / "p.py"; program.write_text(HARNESS)
    altered = tmp_path / "q.py"; altered.write_text(HARNESS.replace("10 // n", "10 // (n or 1)"))
    base = {"function": "f", "suspect_expression": "10 // n", "file": str(tmp_path / "a.py")}
    results = [
        {"hypothesis": {**base, "hypothesis_id": "1"}, "verdict": "NOT_CONFIRMED", "program_path": str(program), "attempts": [{}]},
        {"hypothesis": {**base, "hypothesis_id": "2"}, "verdict": "CONFIRMED", "program_path": str(altered), "attempts": [{}]},
        {"hypothesis": {**base, "hypothesis_id": "3"}, "verdict": "GROUNDING_FAILED", "attempts": []},
    ]

    report = validate_results(results, sources=src, esbmc="esbmc", timeout_seconds=5, work_dir=tmp_path / "w",
                              reach=lambda *a, **k: "unreachable")

    rows = {r["hypothesis_id"]: r for r in report["rows"]}
    assert rows["1"]["validated_verdict"] == "NOT_CONFIRMED_VACUOUS"
    assert rows["2"]["validated_verdict"] == "TARGET_ALTERED"
    assert rows["3"]["checked"] is False
    assert report["summary"]["vacuous"] == 1 and report["summary"]["altered"] == 1
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_verify_validation.py -q -k validate_results`
Expected: FAIL com `ImportError`

- [ ] **Passo 3: implementação**

```python
_REACH_VERDICTS = {"NOT_CONFIRMED", "ESBMC_MISSED", CONFIRMED}
_CHECKED = {"NOT_CONFIRMED", "ESBMC_MISSED", CONFIRMED, "UNVALIDATED", "OTHER_FAILURE"}


def _original(hypothesis: dict, sources: Path) -> str:
    candidate = sources / Path(hypothesis["file"]).name
    return (candidate if candidate.exists() else Path(hypothesis["file"])).read_text(encoding="utf-8")


def validate_results(results: list[dict], *, sources: Path, esbmc: str, timeout_seconds: int, work_dir: Path,
                     control: list[dict] | None = None, with_mutants: bool = False,
                     reach=reachability, run=run_mutant) -> dict:
    rows = []
    for result in results:
        hypothesis = result["hypothesis"]
        row = {"hypothesis_id": hypothesis.get("hypothesis_id"), "verdict": result["verdict"], "checked": False}
        rows.append(row)
        if not result.get("program_path"):
            continue
        attempt = (result.get("attempts") or [{}])[-1]
        replay_path = Path(attempt.get("replay_program_path") or result["program_path"])
        row["checked"] = True
        row["preserved"] = target_preserved(_original(hypothesis, sources), replay_path.read_text(encoding="utf-8"),
                                            hypothesis["function"])
        program = program_for_result(Path(result["program_path"]), hypothesis)
        unwind = attempt.get("unwind") if isinstance(attempt.get("unwind"), int) else 5
        if program is not None and result["verdict"] in _REACH_VERDICTS:
            row["reachability"] = reach(program, esbmc=esbmc, unwind=unwind, timeout_seconds=timeout_seconds,
                                        work_dir=work_dir / f"reach_{row['hypothesis_id']}")
        if with_mutants and program is not None and result["verdict"] in _CHECKED:
            outcomes = [run(m, hypothesis["function"], program.target_range, esbmc_command=[esbmc], bound=unwind,
                            timeout_seconds=timeout_seconds, work_dir=work_dir / f"mut_{row['hypothesis_id']}")
                        for m in mutants(program.source, hypothesis["function"], program.target_spans[0][0])]
            row["mutants"] = {k: outcomes.count(k) for k in (KILLED, SURVIVED, NOT_COUNTED)}
        row["validated_verdict"] = ("TARGET_ALTERED" if not row["preserved"] else
                                    "NOT_CONFIRMED_VACUOUS" if result["verdict"] == "NOT_CONFIRMED"
                                    and row.get("reachability") == UNREACHABLE else result["verdict"])
    checked = [r for r in rows if r["checked"]]
    summary = {"results": len(rows), "with_program": len(checked),
               "altered": sum(not r["preserved"] for r in checked),
               "vacuous": sum(r["validated_verdict"] == "NOT_CONFIRMED_VACUOUS" for r in checked),
               "reachability": {k: sum(r.get("reachability") == k for r in checked)
                                for k in (REACHABLE, UNREACHABLE, INCONCLUSIVE)}}
    if with_mutants:
        summary["mutants"] = {k: sum(r.get("mutants", {}).get(k, 0) for r in checked)
                              for k in (KILLED, SURVIVED, NOT_COUNTED)}
    report = {"rows": rows, "summary": summary}
    if control is not None:
        report["natural_mutation"] = natural_mutation_matrix(results, control)
    return report
```

E o script:

```python
# scripts/v2_validate.py
"""Validate a finished V2 run without the LLM: preservation (V1), reachability of safe verdicts (V2)
and mutation (V3). Writes <run>/validation.json.

  python scripts/v2_validate.py artifacts/v2/<run> [--control <fixed report.json>] [--mutants]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.validation import validate_results  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run")
    parser.add_argument("--sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--control", default=None, help="report of the same hypotheses on the fixed versions")
    parser.add_argument("--mutants", action="store_true")
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()
    run = Path(args.run)
    results = json.loads((run / "v2_verify_report.json").read_text(encoding="utf-8"))["results"]
    control = json.loads(Path(args.control).read_text(encoding="utf-8"))["results"] if args.control else None
    report = validate_results(results, sources=Path(args.sources), esbmc=args.esbmc, timeout_seconds=args.timeout,
                              work_dir=run / "validation", control=control, with_mutants=args.mutants)
    (run / "validation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

E acrescentar `"validation.json"` à tupla `KEEP` de `scripts/archive_runs.py`.

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_verify_validation.py -q`
Expected: PASS

- [ ] **Passo 5: rodar a suíte inteira**

Run: `timeout 600 python3 -m pytest tests/ -q`
Expected: tudo passa

- [ ] **Passo 6: commit (após autorização)**

```bash
git add src/research_pipeline/verify/validation.py scripts/v2_validate.py scripts/archive_runs.py tests/test_verify_validation.py
git commit -m "Validate a finished run's verdicts without calling the LLM"
```

### Tarefa 9: estágio só de detecção (`--v2-stage detection`)

**Files:**
- Modify: `src/main.py:291-292` (opção) e antes do `return _mode_v2_verify(` (linha ~1362)
- Test: `tests/test_main_v2.py`

**Interfaces:**
- Consumes: `evaluate_detection` de `research_pipeline.v2_evaluator`.
- Produces: com `--v2-stage detection`, `v2_verify_report.json` com `coverage = {"status": "complete", "stage": "detection"}`, `detection` igual ao relatório parcial, `evaluation` (ou `None` sem gabarito) e `results = []`; código de saída 0.

- [ ] **Passo 1: teste que falha**

```python
def test_detection_stage_stops_before_verification(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", lambda *a, **k: pytest.fail("verification must not run"))
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
                                           "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    report = json.loads((out / "v2_verify_report.json").read_text())
    assert report["coverage"] == {"status": "complete", "stage": "detection"}
    assert len(report["detection"]["candidates"]) == 1 and report["results"] == []
```

(o arquivo já tem `_Analyzer` e `_Synthesizer`; acrescentar `import json` e `import pytest` se faltarem)

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_main_v2.py -q -k detection_stage`
Expected: FAIL com `argument --v2-stage: invalid choice: 'detection'`

- [ ] **Passo 3: implementação**

Em `build_parser`: `choices=["end-to-end", "synthesis", "detection"]`.

Antes de `return _mode_v2_verify(`, logo depois do bloco que grava o relatório parcial:

```python
    if args.v2_stage == "detection":
        _write_json_atomic(output_path / "llm_telemetry.json", checkpoint["telemetry_events"])
        _write_json_atomic(report_path, {
            "config": config,
            "coverage": {"status": "complete", "stage": "detection"},
            "detection": {
                "analyzed_units": analyzed_units,
                "hypotheses": len(candidates),
                "failed_units": len(detection_errors),
                "errors": detection_errors,
                "candidates": [_v2_candidate_dict(c) for c in candidates],
                "rejected_findings": rejected_findings,
                "trace": detection_trace,
                "trace_summary": _summarize_detection_trace(detection_trace),
            },
            "evaluation": evaluate_detection(candidates=candidates, ground_truth_path=args.ground_truth,
                                             evaluated_sources=input_paths, rejected_findings=rejected_findings)
            if args.ground_truth else None,
            "telemetry": _summarize_v2_telemetry(checkpoint["telemetry_events"]),
            "results": [],
        })
        print(f"Detecção concluída: {len(candidates)} hipótese(s) enviada(s), {len(rejected_findings)} segurada(s).")
        return 0
```

com `from research_pipeline.v2_evaluator import evaluate_detection` nos imports do `main.py`. Conferir antes, com `grep -n "capture_telemetry()" src/main.py`, se a telemetria já foi capturada nesse ponto; se não, chamar `capture_telemetry()` na primeira linha do bloco.

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_main_v2.py -q`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add src/main.py tests/test_main_v2.py
git commit -m "Add a detection-only V2 stage for prompt experiments"
```

### Tarefa 10: variantes do prompt (`--v2-variants`)

**Files:**
- Create: `src/research_pipeline/llm/prompt_variants.py`
- Create: `src/research_pipeline/prompts/v2_variants/A2_checklist.txt`
- Modify: `src/research_pipeline/llm/prompts.py:53-61` (`load_system_prompt`)
- Modify: os 5 backends e `factory.py` (passar `v2_variants`)
- Modify: `src/main.py` (opção, `build_analyzer`, `config`)
- Test: `tests/test_prompt_variants.py`, `tests/test_main_v2.py`

**Interfaces:**
- Produces: `VARIANTS: dict[str, Callable[[str], str]]` com `"A1"`, `"A2"`, `"A3"`; `apply_variants(prompt: str, names: tuple[str, ...]) -> str`; `load_system_prompt(..., v2_variants: tuple[str, ...] = ())`; `build_analyzer(..., v2_variants: tuple[str, ...] = ())`; `config["v2_variants"]: list[str]`.

- [ ] **Passo 1: testes que falham**

```python
# tests/test_prompt_variants.py
import pytest

from research_pipeline.llm.prompt_variants import VARIANTS, apply_variants
from research_pipeline.llm.prompts import load_system_prompt

BASE = load_system_prompt(include_smells=False, v2_detection=True)


def test_without_variants_the_prompt_is_the_baseline() -> None:
    assert apply_variants(BASE, ()) == BASE


def test_a1_asks_to_report_even_without_context() -> None:
    changed = apply_variants(BASE, ("A1",))
    assert "prefira não reportar" not in changed and "quando apropriado, não reporte" not in changed


def test_a2_adds_the_input_checklist_before_the_output_section() -> None:
    changed = apply_variants(BASE, ("A2",))
    assert changed.index("## PARTIÇÃO DE ENTRADAS") < changed.index("## SAÍDA")


def test_a3_asks_for_ranked_hypotheses() -> None:
    assert "da mais para a menos provável" in apply_variants(BASE, ("A3",))


def test_variants_compose() -> None:
    both = apply_variants(BASE, ("A1", "A2"))
    assert "## PARTIÇÃO DE ENTRADAS" in both and "prefira não reportar" not in both


def test_a_variant_whose_anchor_is_gone_fails_loudly() -> None:
    with pytest.raises(ValueError, match="A1"):
        apply_variants("prompt sem os trechos", ("A1",))


def test_an_unknown_variant_fails() -> None:
    with pytest.raises(ValueError, match="Z9"):
        apply_variants(BASE, ("Z9",))


def test_load_system_prompt_applies_variants() -> None:
    assert "## PARTIÇÃO DE ENTRADAS" in load_system_prompt(include_smells=False, v2_detection=True, v2_variants=("A2",))
```

E em `tests/test_main_v2.py`:

```python
def test_variants_enter_the_run_config(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    seen = {}
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: seen.update(kwargs) or _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    out = tmp_path / "out"
    args = main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--v2-variants", "A1,A2",
                                           "--input", str(source), "--output-dir", str(out)])

    assert main.mode_v2(args) == 0
    assert seen["v2_variants"] == ("A1", "A2")
    assert json.loads((out / "v2_verify_report.json").read_text())["config"]["v2_variants"] == ["A1", "A2"]
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_prompt_variants.py tests/test_main_v2.py -q -k "variant"`
Expected: FAIL com `ModuleNotFoundError: research_pipeline.llm.prompt_variants`

- [ ] **Passo 3: implementação**

```python
# src/research_pipeline/llm/prompt_variants.py
"""Named changes to the V2 detection prompt, measured one at a time against the baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

_DIR = Path(__file__).resolve().parents[1] / "prompts" / "v2_variants"


def _swap(name: str, prompt: str, old: str, new: str) -> str:
    if old not in prompt:
        raise ValueError(f"variant {name}: anchor not found in the V2 prompt: {old[:40]!r}")
    return prompt.replace(old, new)


def _report_without_context(prompt: str) -> str:
    prompt = _swap("A1", prompt, "`metadata.context_needed` e, quando apropriado, não reporte o achado.",
                   "`metadata.context_needed` e reporte o achado mesmo assim.")
    return _swap("A1", prompt, "`metadata.context_needed` para indicar o que falta e prefira não reportar o\nachado.",
                 "`metadata.context_needed` para indicar o que falta e reporte o achado: o\nESBMC e a reexecução decidem.")


def _input_checklist(prompt: str) -> str:
    return _swap("A2", prompt, "## SAÍDA: JSON válido", (_DIR / "A2_checklist.txt").read_text(encoding="utf-8")
                 + "\n## SAÍDA: JSON válido")


def _ranked(prompt: str) -> str:
    return _swap("A3", prompt,
                 "A saída pode conter zero, uma ou várias hipóteses: não existe quantidade mínima\n"
                 "nem máxima fixa.",
                 "Liste até 5 hipóteses por função, da mais para a menos provável de ser um bug\n"
                 "real; zero é uma resposta válida.")


VARIANTS: dict[str, Callable[[str], str]] = {"A1": _report_without_context, "A2": _input_checklist, "A3": _ranked}


def apply_variants(prompt: str, names: tuple[str, ...]) -> str:
    for name in names:
        if name not in VARIANTS:
            raise ValueError(f"unknown V2 prompt variant {name!r}; known: {sorted(VARIANTS)}")
        prompt = VARIANTS[name](prompt)
    return prompt
```

```text
# src/research_pipeline/prompts/v2_variants/A2_checklist.txt
## PARTIÇÃO DE ENTRADAS

Antes do item 1, percorra cada parâmetro e cada atributo de `self` que a função
lê e pergunte, um por um, o que acontece quando ele é:
- None (inclusive quando o padrão do parâmetro é None ou o nome sugere opcional);
- vazio (string, lista, dicionário, conjunto);
- zero ou negativo;
- de outro tipo plausível (bytes no lugar de str, int no lugar de str, lista no lugar de tupla);
- uma chave ausente num dicionário, ou um índice fora do intervalo.
Cada caso que leva a uma exceção ou a um resultado errado e passa pelas guardas
existentes é uma hipótese.
```

Em `prompts.py`:

```python
@lru_cache(maxsize=16)
def load_system_prompt(*, include_smells: bool = True, v2_detection: bool = False,
                       v2_variants: tuple[str, ...] = ()) -> str:
    ...
    if v2_detection:
        base = (PROMPTS_DIR / "system_prompt_v2.txt").read_text(encoding="utf-8").strip()
        return apply_variants(base, v2_variants)
```

com `from .prompt_variants import apply_variants`.

Backends e fábrica (troca mecânica, conferir com `git diff` depois):

```bash
for f in src/research_pipeline/llm/backends/{anthropic,openai,chat_completions,claude_cli,codex}.py; do
  sed -i 's/^        v2_detection: bool = False,$/        v2_detection: bool = False,\n        v2_variants: tuple[str, ...] = (),/' "$f"
  sed -i 's/^        self.v2_detection = v2_detection$/        self.v2_detection = v2_detection\n        self.v2_variants = v2_variants/' "$f"
  sed -i 's/load_system_prompt(include_smells=self.include_smells, v2_detection=self.v2_detection)/load_system_prompt(include_smells=self.include_smells, v2_detection=self.v2_detection, v2_variants=self.v2_variants)/' "$f"
done
f=src/research_pipeline/llm/backends/factory.py
sed -i 's/^    v2_detection: bool = False,$/    v2_detection: bool = False,\n    v2_variants: tuple[str, ...] = (),/' "$f"
sed -i 's/v2_detection=v2_detection,/v2_detection=v2_detection, v2_variants=v2_variants,/; s/v2_detection=v2_detection)/v2_detection=v2_detection, v2_variants=v2_variants)/' "$f"
grep -c "v2_variants" src/research_pipeline/llm/backends/*.py
```

Expected no `grep`: 3 em cada backend, 7 em `factory.py`.

Em `main.py`: opção

```python
    parser.add_argument(
        "--v2-variants", default="", metavar="A1,A2",
        help="Variantes do prompt V2 (ver research_pipeline/llm/prompt_variants.py), aplicadas em ordem.",
    )
```

`variants = tuple(v for v in args.v2_variants.split(",") if v)` no começo de `mode_v2`; `v2_variants=variants` na chamada de `build_analyzer` (linha ~1154); `"v2_variants": list(variants),` no dicionário `config` (linha ~1184), que entra na impressão digital da retomada.

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_prompt_variants.py tests/test_main_v2.py tests/test_v2_taxonomy.py -q`
Expected: PASS

- [ ] **Passo 5: suíte inteira**

Run: `timeout 600 python3 -m pytest tests/ -q`
Expected: tudo passa

- [ ] **Passo 6: commit (após autorização)**

```bash
git add src/research_pipeline/llm src/research_pipeline/prompts/v2_variants src/main.py tests/test_prompt_variants.py tests/test_main_v2.py
git commit -m "Select V2 detection prompt variants by name"
```

### Tarefa 11: união de várias detecções (variante A4)

**Files:**
- Create: `scripts/v2_union_detection.py`
- Test: `tests/test_v2_union_detection.py`

**Interfaces:**
- Consumes: relatórios de `--v2-stage detection` (Tarefa 9); `evaluate_detection`; `Candidate.from_dict`.
- Produces: `union(reports: list[dict]) -> tuple[list[Candidate], list[dict]]` (achados enviados e segurados, sem repetir a mesma `(arquivo, função, expressão)`).

- [ ] **Passo 1: teste que falha**

```python
# tests/test_v2_union_detection.py
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("union", Path(__file__).parents[1] / "scripts" / "v2_union_detection.py")
union_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(union_module)


def _report(sent, held):
    return {"detection": {"candidates": [{"file": "a.py", "function": "f", "expression": e} for e in sent],
                          "rejected_findings": [{"file": "a.py", "function": "f", "expression": e} for e in held]}}


def test_union_keeps_each_finding_once_and_prefers_sent() -> None:
    sent, held = union_module.union([_report(["x[0]"], ["y.z"]), _report(["y.z", "x[0]"], ["w"])])
    assert sorted(c.expression for c in sent) == ["x[0]", "y.z"]
    assert [h["expression"] for h in held] == ["w"]
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `python3 -m pytest tests/test_v2_union_detection.py -q`
Expected: FAIL (arquivo não existe)

- [ ] **Passo 3: implementação**

```python
# scripts/v2_union_detection.py
"""Union of several detection-only runs (variant A4): a finding sent by any run counts as sent.

  python scripts/v2_union_detection.py <run1> <run2> <run3> --out <union.json>
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.v2_evaluator import evaluate_detection  # noqa: E402
from research_pipeline.verify.candidate import Candidate  # noqa: E402


def _key(item: dict) -> tuple[str, str, str]:
    return str(Path(item["file"]).resolve()), item["function"], item.get("expression", "")


def union(reports: list[dict]) -> tuple[list[Candidate], list[dict]]:
    sent: dict = {}
    held: dict = {}
    for report in reports:
        for item in report["detection"]["candidates"]:
            sent.setdefault(_key(item), item)
        for item in report["detection"]["rejected_findings"]:
            held.setdefault(_key(item), item)
    return [Candidate.from_dict(i) for i in sent.values()], [i for k, i in held.items() if k not in sent]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("runs", nargs="+")
    parser.add_argument("--ground-truth", default="dataset/bugs_reais/ground_truths.json")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    reports = [json.loads((Path(r) / "v2_verify_report.json").read_text(encoding="utf-8")) for r in args.runs]
    sent, held = union(reports)
    sources = sorted({str(Path(p).resolve()) for r in reports for p in r["config"]["input_files"]})
    evaluation = evaluate_detection(candidates=sent, ground_truth_path=args.ground_truth,
                                    evaluated_sources=sources, rejected_findings=held)
    Path(args.out).write_text(json.dumps({"runs": args.runs, "sent": len(sent), "held": len(held),
                                          "evaluation": evaluation}, indent=2), encoding="utf-8")
    print(json.dumps({"sent": len(sent), "held": len(held)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Passo 4: rodar e ver passar**

Run: `python3 -m pytest tests/test_v2_union_detection.py -q`
Expected: PASS

- [ ] **Passo 5: commit (após autorização)**

```bash
git add scripts/v2_union_detection.py tests/test_v2_union_detection.py
git commit -m "Evaluate the union of several detection runs"
```

### Tarefa 12: rodadas (depois que o agente terminar)

Sem código novo; só execução e registro. Cada rodada: lançar desacoplada (`setsid nohup`), registrar em `docs/experimentos/README.md` (fase 9), arquivar com `python scripts/archive_runs.py <pasta> --fase 9`.

Comando de detecção (troque `<V>` e `<pasta>`):

```bash
PYTHONPATH=src .venv/bin/python -u src/main.py --mode hybrid --v2-stage detection \
  --input dataset/bugs_reais/funcao_com_bug --ground-truth dataset/bugs_reais/ground_truths.json \
  --backend claude_cli --model claude-sonnet-5-5 --synth-backend claude_cli --synth-model claude-sonnet-5-5 \
  --v2-variants "<V>" --output-dir artifacts/v2/<pasta>
```

- [ ] **Passo 1:** arquivar a rodada do agente: `python scripts/archive_runs.py agent-2026-10-06-e2e --fase 8` e atualizar o README (resultado final do agente).
- [ ] **Passo 2:** validação: `python scripts/v2_validate.py artifacts/v2/full-2026-10-05-regrounded --control artifacts/v2/control-fixed-2026-10-06/report_0of1.json --mutants`; registrar preservação, vacuidade e mutação.
- [ ] **Passo 3:** A0 de novo (`--v2-variants ""`, pasta `detect-2026-10-xx-A0-r2`); a diferença entre esta e a detecção de `full-2026-10-04-sonnet` é a variação da LLM.
- [ ] **Passo 4:** A1, A2, A3 (uma pasta cada); A4 = três rodadas A0 (`-A0-r2`, `-A0-r3`, `-A0-r4`) e `python scripts/v2_union_detection.py <as três> --out artifacts/v2/detect-A4-union.json`.
- [ ] **Passo 5:** tabela por variante e tipo de bug (função certa, linha certa, nada reportado, achados por função) no README; aceite = linha certa nos que quebram acima da variação de A0, sem dobrar os achados por função.
- [ ] **Passo 6:** A5 = melhores variantes juntas; rodada completa (`--v2-stage end-to-end`), agente nas travadas, controle nas versões corrigidas e `v2_validate.py` em cima; registrar e arquivar.
