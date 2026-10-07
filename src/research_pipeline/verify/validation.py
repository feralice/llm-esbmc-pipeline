"""Whether a verify verdict means what it says: the target is the original code (V1), a "safe"
verdict examined the hypothesis line (V2), and the harness catches faults injected near it (V3)."""

from __future__ import annotations

import ast
import copy
from pathlib import Path
from typing import NamedTuple

from .astutil import body_signature, expression_nodes, find_function
from .esbmc_run import check, esbmc_output
from .outcome import CONFIRMED
from .procs import run_group
from .render import Program
from .replay import concrete_replay, counterexample_seeds

REACHABLE, UNREACHABLE, INCONCLUSIVE = "reachable", "unreachable", "inconclusive"
_REACH = "reachability: unreachable code reached"


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


class _AsStubs(ast.NodeTransformer):
    """``re.sub`` -> ``_esbmc_re_sub`` where the program uses that stub (slicing's refused-member rename)."""

    def __init__(self, stubs: set[str]) -> None:
        self.stubs = stubs

    def visit_Attribute(self, node: ast.Attribute) -> ast.AST:
        name = "_esbmc_" + ast.unparse(node).replace(".", "_")
        return ast.Name(name, node.ctx) if name in self.stubs else self.generic_visit(node)


def target_preserved(original_source: str, program_source: str, function: str) -> bool:
    original = find_function(ast.parse(original_source), function)
    checked = find_function(ast.parse(program_source), function)
    if original is None or checked is None:
        return False
    stubs = {n.id for n in ast.walk(checked) if isinstance(n, ast.Name) and n.id.startswith("_esbmc_")}
    return body_signature(_AsStubs(stubs).visit(original)) == body_signature(checked)


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


_REACH_VERDICTS = {"NOT_CONFIRMED", "ESBMC_MISSED", CONFIRMED}
_CHECKED = {"NOT_CONFIRMED", "ESBMC_MISSED", CONFIRMED, "UNVALIDATED", "OTHER_FAILURE"}


def _original(hypothesis: dict, sources: Path) -> str:
    candidate = sources / Path(hypothesis["file"]).name
    return (candidate if candidate.exists() else Path(hypothesis["file"])).read_text(encoding="utf-8")


def _replay_program(result: dict) -> Path | None:
    """The pre-rewrite program of the attempt the verdict came from; None when a catalogue rewrite
    left no replay program (preservation is then unknown, not altered)."""
    program = Path(result["program_path"])
    for attempt in result.get("attempts") or []:
        replay = attempt.get("replay_program_path")
        if replay and Path(replay).stem.startswith(program.stem):
            return Path(replay)
    if any(str(t).startswith("compat_") for t in result.get("transforms") or []):
        return None
    return program


def _validate_row(result: dict, row: dict, *, sources: Path, esbmc: str, timeout_seconds: int, work_dir: Path,
                  with_mutants: bool, reach, run) -> None:
    hypothesis = result["hypothesis"]
    row["checked"] = True
    replay_path = _replay_program(result)
    row["preserved"] = None if replay_path is None else target_preserved(
        _original(hypothesis, sources), replay_path.read_text(encoding="utf-8"), hypothesis["function"])
    program = program_for_result(Path(result["program_path"]), hypothesis)
    attempt = (result.get("attempts") or [{}])[-1]
    unwind = attempt.get("unwind") if isinstance(attempt.get("unwind"), int) else 5
    if program is not None and result["verdict"] in _REACH_VERDICTS:
        row["reachability"] = reach(program, esbmc=esbmc, unwind=unwind, timeout_seconds=timeout_seconds,
                                    work_dir=work_dir / f"reach_{row['hypothesis_id']}")
    # A program that already violates gets every mutant "killed" by its own bug: score safe verdicts only.
    if with_mutants and program is not None and result["verdict"] == "NOT_CONFIRMED":
        outcomes = [run(m, hypothesis["function"], program.target_range, esbmc_command=[esbmc], bound=unwind,
                        timeout_seconds=timeout_seconds, work_dir=work_dir / f"mut_{row['hypothesis_id']}")
                    for m in mutants(program.source, hypothesis["function"], program.target_spans[0][0])]
        row["mutants"] = {k: outcomes.count(k) for k in (KILLED, SURVIVED, NOT_COUNTED)}
    row["validated_verdict"] = ("TARGET_ALTERED" if row["preserved"] is False else
                                "NOT_CONFIRMED_VACUOUS" if result["verdict"] == "NOT_CONFIRMED"
                                and row.get("reachability") == UNREACHABLE else result["verdict"])


def validate_results(results: list[dict], *, sources: Path, esbmc: str, timeout_seconds: int, work_dir: Path,
                     control: list[dict] | None = None, with_mutants: bool = False,
                     reach=reachability, run=run_mutant) -> dict:
    rows = []
    for result in results:
        row = {"hypothesis_id": result["hypothesis"].get("hypothesis_id"), "verdict": result["verdict"],
               "checked": False}
        rows.append(row)
        if not result.get("program_path") or result["verdict"] not in _CHECKED:
            continue
        try:
            _validate_row(result, row, sources=sources, esbmc=esbmc, timeout_seconds=timeout_seconds,
                          work_dir=work_dir, with_mutants=with_mutants, reach=reach, run=run)
        except Exception as exc:  # noqa: BLE001 - one bad row must not discard hours of ESBMC runs
            row.update(checked=False, error=f"{type(exc).__name__}: {exc}")
    checked = [r for r in rows if r["checked"]]
    summary = {"results": len(rows), "with_program": len(checked), "errors": sum("error" in r for r in rows),
               "altered": sum(r["preserved"] is False for r in checked),
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
