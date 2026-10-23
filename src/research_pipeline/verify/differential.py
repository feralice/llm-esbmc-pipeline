"""Differential test: does the harness behave like the original code on the bug path?

The stubs level runs each input sequence through the harness and through the harness with the original
target body, comparing status, exception type and the line, relative to the target, where the exception
crosses it. Only the real level (the true module, imported without network) can call behaviour preserved.
"""

from __future__ import annotations

import ast
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import agent_arm
from .hypothesis import BugHypothesis
from .render import Program
from .replay import ReplayVerdict, _no_network_prefix, concrete_replay
from .sandbox import host_replay_problem, process_limits

PRESERVED, CHANGED, NOT_MEASURED = "preservada", "alterada", "nao_medida"


@dataclass
class DiffResult:
    level: str  # real | stubs
    agreed: int
    total: int
    divergences: list[dict] = field(default_factory=list)
    preservation: str = NOT_MEASURED  # preservada | alterada | nao_medida
    reason: str = ""  # why the real level did not run

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class _Frame:
    """Where the target sits in one program. Lines before it are shared and lines after it shift by the
    body's length; inside it a line is named by its text, so a body that dropped a statement still lines
    up with the original."""
    first: int
    end: int
    text: tuple[str, ...]

    @classmethod
    def of(cls, source: str, node: ast.FunctionDef, first: int | None = None) -> _Frame:
        start = agent_arm._first_line(node)
        lines = source.splitlines()[start - 1:node.end_lineno]
        first = start if first is None else first
        return cls(first, first + len(lines) - 1, tuple(line.strip() for line in lines))

    def place(self, line: int | None) -> list | None:
        if line is None:
            return None
        if line < self.first:
            return ["before", line]
        if line > self.end:
            return ["after", line - self.end]
        return ["target", self.text[line - self.first]]


def _outcome(verdict: ReplayVerdict, frame: _Frame) -> dict:
    return {"status": verdict.status, "exception_type": verdict.exception_type,
            "line": frame.place(verdict.line), "raised_at": frame.place(verdict.raised_at)}


# A fixed sequence that one side consumes differently means the two sides took different paths.
_PATH_MISMATCH = ("the program asked for more values", "the fixed input has more values")


def _comparable(verdict: ReplayVerdict) -> bool:
    return verdict.status != "unavailable" or verdict.reason.startswith(_PATH_MISMATCH)


class _Sides:
    """The harness as ESBMC checked it, and the same harness with the original target body."""

    def __init__(self, harness: str, original: str, target: ast.FunctionDef, original_target: ast.FunctionDef):
        self.harness, self.original = harness, original
        self.target, self.original_target = target, original_target
        span = (target.lineno, target.end_lineno or target.lineno)
        self.program = Program(agent_arm._without_esbmc_imports(harness), 0, (span,), (), span)
        self.harness_frame = _Frame.of(harness, target)
        self.original_frame = _Frame.of(original, self.original_target, first=self.harness_frame.first)

    def run_original(self, **kwargs) -> ReplayVerdict:
        verdict, _ = agent_arm._replay_original(self.harness, self.target, self.original, self.original_target,
                                                None, kwargs.pop("seeds", {}), **kwargs)
        return verdict

    def sequences(self, seeds: dict[str, list], runs: int) -> list[list]:
        """ESBMC's counterexample first, then random runs; a run that ends normally reports no inputs, so
        each source is tried on both sides."""
        found: list[list] = []
        def add(verdict: ReplayVerdict) -> bool:
            if verdict.inputs is None:
                return False
            if verdict.inputs not in found:
                found.append(verdict.inputs)
            return True
        if any(seeds.values()):
            add(concrete_replay(self.program, self.target.name, seeds=seeds, seeds_only=True))
            add(self.run_original(seeds=seeds))
        for i in range(runs):
            if not add(concrete_replay(self.program, self.target.name, max_runs=0, random_runs=1, seed=i)):
                add(self.run_original(random_seed=i))
        return found

    def compare(self, inputs: list) -> dict | None:
        harness = concrete_replay(self.program, self.target.name, inputs=inputs)
        original = self.run_original(inputs=inputs)
        if not (_comparable(harness) and _comparable(original)) or harness.status == original.status == "unavailable":
            return None
        return {"inputs": inputs, "harness": _outcome(harness, self.harness_frame),
                "original": _outcome(original, self.original_frame)}


def differential(harness: str, original: str, h: BugHypothesis, seeds: dict[str, list], runs: int = 100,
                 original_path: Path | None = None) -> DiffResult:
    """Any divergence is ``alterada``; without one the stubs level leaves preservation ``nao_medida``."""
    try:
        target = agent_arm._target(ast.parse(harness), h.function)
        original_target = agent_arm._target(ast.parse(original), h.function)
    except SyntaxError as exc:
        return DiffResult("stubs", 0, 0, reason=f"does not parse: {exc.msg}")
    if target is None or original_target is None:
        return DiffResult("stubs", 0, 0, reason=f"target {h.function} missing")
    sides = _Sides(harness, original, target, original_target)
    sequences = sides.sequences(seeds, runs)
    compared = [c for c in map(sides.compare, sequences) if c is not None]
    divergences = [c for c in compared if c["harness"] != c["original"]]
    stubs = DiffResult("stubs", len(compared) - len(divergences), len(compared), divergences,
                       CHANGED if divergences else NOT_MEASURED)
    if divergences or original_path is None:
        return stubs
    real, why = _real_level(sides, Path(original_path), h.function, sequences)
    if real is None:
        stubs.reason = why
        return stubs
    return real


_SCALARS = frozenset({"int", "float", "bool", "str"})
REAL_TIMEOUT = 60


def _real_problem(sides: _Sides, module: ast.Module, function: str) -> str:
    """Why the real level cannot run, or "": it takes free functions with scalar parameters only."""
    real = next((n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == function), None)
    if "." in function or real is None:
        return f"{function} is not a free function of the original module"
    if real.decorator_list or sides.target.decorator_list:
        return "decorated target"
    parameters = sides.target.args
    if parameters.vararg or parameters.kwarg or parameters.kwonlyargs or real.args.vararg or real.args.kwarg:
        return "target takes variable or keyword-only arguments"
    names = [a.annotation.id if isinstance(a.annotation, ast.Name) else None
             for a in [*parameters.posonlyargs, *parameters.args]]
    if not set(names) <= _SCALARS:
        return "target has parameters other than int, float, bool, str"
    if len(names) != len(real.args.posonlyargs) + len(real.args.args):
        return "harness and original targets take different parameters"
    if not _no_network_prefix():
        return "no network namespace on this host"
    return host_replay_problem(sides.program.source)


def _real_level(sides: _Sides, path: Path, function: str, sequences: list[list]) -> tuple[DiffResult | None, str]:
    """Compare the harness's target with the original module's function, called with the arguments the
    driver passes for each sequence; (None, reason) when the original cannot be measured."""
    try:
        source = path.read_text(encoding="utf-8")
        module = ast.parse(source)
    except (OSError, UnicodeDecodeError, SyntaxError) as exc:
        return None, f"original not readable: {type(exc).__name__}"
    problem = _real_problem(sides, module, function)
    if problem:
        return None, problem
    real_target = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == function)
    worker = Path(__file__).with_name("differential_worker.py")
    config = {"function": function, "module": str(path.resolve()), "sequences": sequences,
              "range": [agent_arm._first_line(sides.target), sides.target.end_lineno]}
    try:
        with tempfile.TemporaryDirectory(prefix="llm-esbmc-differential-") as temp_dir:
            directory = Path(temp_dir)
            (directory / "program.py").write_text(sides.program.source, encoding="utf-8")
            (directory / "config.json").write_text(json.dumps(config), encoding="utf-8")
            output = directory / "result.json"
            completed = subprocess.run(
                [*_no_network_prefix(), sys.executable, "-I", "-S", str(worker), "program.py", "config.json",
                 str(output)],
                cwd=directory, env={}, capture_output=True, text=True, timeout=REAL_TIMEOUT, check=False,
                preexec_fn=process_limits(REAL_TIMEOUT),
            )
            if not output.exists():
                return None, f"real run gave no result: {(completed.stderr or '')[-300:]}"
            data = json.loads(output.read_text(encoding="utf-8"))
    except subprocess.TimeoutExpired:
        return None, "real run timed out"
    except (OSError, ValueError) as exc:
        return None, f"real run failed: {type(exc).__name__}"
    if "import_error" in data:
        return None, f"original does not import: {data['import_error']}"
    compared = [r for r in data["results"] if r is not None
                and "timeout" not in (r["harness"]["status"], r["real"]["status"])]
    if not compared:
        return None, "no sequence reached the target"
    real_frame = _Frame.of(source, real_target)
    for r in compared:
        r["harness"]["line"] = sides.harness_frame.place(r["harness"]["line"])
        r["real"]["line"] = real_frame.place(r["real"]["line"])
    divergences = [r for r in compared if r["harness"] != r["real"]]
    return DiffResult("real", len(compared) - len(divergences), len(compared), divergences,
                      CHANGED if divergences else PRESERVED), ""
