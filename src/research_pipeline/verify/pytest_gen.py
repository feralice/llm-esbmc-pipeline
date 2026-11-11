"""A pytest reproducer for a confirmed bug, written by ESBMC's own generator and checked by running it.

ESBMC's --generate-pytest-testcase (https://esbmc.github.io/docs/python/pytest-testgen/) writes a
parametrized test from its counterexample. Measured on ESBMC 8.5 and master (2026-10-01), it only
emits a usable test for a free function called with ``__VERIFIER_nondet_*()`` arguments: with a
receiver it prints internal names (``x&0#1``), and it can produce calls with the wrong arity. So the
program is rewritten into that shape, the test is run under pytest, and it is kept only when it
fails with the bug's exception, which is how ESBMC's tests show a bug (they carry no assert).
"""

from __future__ import annotations

import ast
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from .render import DRIVER, Program
from .source_replay import without_esbmc_imports
from .replay import _no_network_prefix
from .sandbox import host_replay_problem, process_limits
from .spec import parse_type

_SCALARS = {"int", "float", "bool", "str"}
ESBMC_WRONG_ARITY = "ESBMC's test passes"


def _source_without_driver(source: str) -> list[str]:
    lines = source.splitlines()
    return lines[:lines.index(f"def {DRIVER}() -> None:")]


def pytest_reproducer(program: Program, *, function: str, params: dict[str, str], exception: str,
                      esbmc_command: list[str], bound: int, out_dir: Path, name: str,
                      timeout_seconds: int = 120, coroutine: bool = False) -> dict:
    """Try ESBMC's generator on the confirmed program; returns {"status", "path", "reason"}. A ``coroutine``
    is called through ``asyncio.run`` in the program and in the test, which ESBMC writes as a plain call."""
    if "." in function:
        return {"status": "unsupported_shape", "path": "", "reason": "ESBMC's generator handles free functions only"}
    types = [parse_type(text) for text in params.values()]
    if any(t is None or t.kind not in _SCALARS or t.optional for t in types):
        return {"status": "unsupported_shape", "path": "", "reason": "ESBMC's generator here needs scalar inputs"}
    out_dir.mkdir(parents=True, exist_ok=True)
    module = out_dir / f"{name}.py"
    call = f"{function}({', '.join(f'__VERIFIER_nondet_{t.kind}()' for t in types)})"
    if coroutine:
        call = f"asyncio.run({call})"
    module.write_text("\n".join([*_source_without_driver(program.source), call]) + "\n",
                      encoding="utf-8")
    test = out_dir / f"test_{name}.py"
    test.unlink(missing_ok=True)
    try:
        subprocess.run([*esbmc_command, str(module), "--unwind", str(bound), "--no-slice",
                        "--no-unwinding-assertions", "--generate-pytest-testcase", "--pytest-output-dir",
                        str(out_dir)], capture_output=True, text=True,
                       timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "not_generated", "path": "", "reason": f"ESBMC did not finish: {type(exc).__name__}"}
    if not test.exists():
        return {"status": "not_generated", "path": "", "reason": "ESBMC wrote no test"}
    try:
        ast.parse(test.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return {"status": "invalid", "path": str(test), "reason": f"ESBMC wrote invalid Python: {exc.msg}"}
    wrong_arity = _arity_problem(test.read_text(encoding="utf-8"), function, len(types))
    if wrong_arity:
        return {"status": "invalid", "path": str(test), "reason": wrong_arity}
    if coroutine:
        test.write_text(awaited_test(test.read_text(encoding="utf-8"), function), encoding="utf-8")
    # The test imports the module: CPython gets the replayed program (real exceptions), without the call.
    library = "\n".join(_source_without_driver(program.replay_source or program.source)) + "\n"
    return _run_generated_test(test, module, library, exception)


def _arity_problem(test: str, function: str, arity: int) -> str | None:
    """Report calls with a different number of positional arguments than expected."""
    for node in ast.walk(ast.parse(test)):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == function
                and len(node.args) != arity):
            return f"{ESBMC_WRONG_ARITY} {len(node.args)} arguments to {function}(), which takes {arity}"
    return None


def awaited_test(test: str, function: str) -> str:
    """ESBMC's test with each statement-level call of ``function`` run by ``asyncio.run``."""
    tree = ast.parse(test)
    for node in ast.walk(tree):
        if (isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
                and isinstance(node.value.func, ast.Name) and node.value.func.id == function):
            node.value = ast.Call(ast.Attribute(ast.Name("asyncio", ast.Load()), "run", ast.Load()), [node.value], [])
    return "import asyncio\n" + ast.unparse(ast.fix_missing_locations(tree)) + "\n"


def _run_generated_test(test: Path, module: Path, library: str, exception: str) -> dict:
    """Run ESBMC's test against ``library`` (the module without its call); accept it only when it fails
    with ``exception``."""
    problem = host_replay_problem(library)
    if problem:
        return {"status": "not_run", "path": str(test), "reason": f"not executed on host: {problem}"}
    module.write_text(library, encoding="utf-8")
    worker = Path(__file__).with_name("pytest_worker.py")
    try:
        with tempfile.TemporaryDirectory(prefix="llm-esbmc-pytest-") as scratch:
            directory = Path(scratch)
            (directory / module.name).write_text(library, encoding="utf-8")
            (directory / test.name).write_text(test.read_text(encoding="utf-8"), encoding="utf-8")
            done = subprocess.run([*_no_network_prefix(), sys.executable, "-I", str(worker), test.name],
                                  cwd=directory, capture_output=True, text=True, timeout=60, check=False,
                                  env={"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1", "PYTHONDONTWRITEBYTECODE": "1"},
                                  preexec_fn=process_limits(60))
    except subprocess.TimeoutExpired:
        return {"status": "invalid", "path": str(test), "reason": "pytest timed out"}
    output = done.stdout + done.stderr
    if done.returncode == 125:
        return {"status": "not_run", "path": str(test), "reason": output.strip()[:300]}
    tail = " ".join(output.strip().splitlines()[-2:])[:300]
    if "No module named pytest" in output:
        return {"status": "not_run", "path": str(test), "reason": "pytest is not installed"}
    if f"- {exception}" in output or f"E   {exception}" in output:
        return {"status": "reproduces", "path": str(test), "reason": f"pytest fails with {exception}"}
    if done.returncode == 0:
        return {"status": "does_not_reproduce", "path": str(test), "reason": tail}
    # Any other failure (a missing argument, an import error) is a defect of the generated test.
    return {"status": "invalid", "path": str(test), "reason": tail}


def _cpython_source(nodes: list[ast.stmt]) -> str:
    return without_esbmc_imports(ast.unparse(ast.Module(nodes, [])))


def _driver_call(tree: ast.Module) -> tuple[ast.FunctionDef, ast.Expr, ast.Call] | None:
    """The driver (a no-argument function called at module level) and its final call, whose arguments
    are rewritten to hold the nondet calls inline: the only shape the generator names correctly."""
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    for statement in tree.body:
        call = statement.value if isinstance(statement, ast.Expr) else None
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and not call.args:
            driver = functions.get(call.func.id)
            if driver is not None and not driver.args.args:
                break
    else:
        return None
    nondet: dict[str, ast.expr] = {}
    for node in driver.body[:-1]:
        target = node.target if isinstance(node, ast.AnnAssign) else node.targets[0] if (
            isinstance(node, ast.Assign) and len(node.targets) == 1) else None
        value = getattr(node, "value", None)
        if not (isinstance(target, ast.Name) and isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
                and value.func.id.startswith("nondet_") and not value.args):
            return None
        nondet[target.id] = value
    last = driver.body[-1] if driver.body else None
    if not (isinstance(last, ast.Expr) and isinstance(last.value, ast.Call) and not last.value.keywords):
        return None
    inline = ast.Call(func=last.value.func, args=[nondet.get(a.id, a) if isinstance(a, ast.Name) else a
                                                  for a in last.value.args], keywords=[])
    return driver, ast.Expr(inline), inline


def _direct_test(tree: ast.Module, *, name: str, esbmc_command: list[str], bound: int, out_dir: Path,
                 exception: str, timeout_seconds: int) -> dict:
    found = _driver_call(tree)
    if found is None:
        return {"status": "not_generated", "path": "", "reason": "harness shape not recognised"}
    driver, call, inline = found
    if not isinstance(inline.func, ast.Name) or any(isinstance(a, ast.Call) and not (
            isinstance(a.func, ast.Name) and a.func.id.startswith("nondet_")) for a in inline.args):
        return {"status": "not_generated", "path": "", "reason": "the call is not a free function of inputs"}
    rest = [n for n in tree.body if n is not driver and not (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == driver.name)]
    module = out_dir / f"{name}.py"
    module.write_text(ast.unparse(ast.Module([*rest, call], [])) + "\n", encoding="utf-8")
    test = out_dir / f"test_{name}.py"
    test.unlink(missing_ok=True)
    try:
        subprocess.run([*esbmc_command, str(module), "--unwind", str(bound), "--no-slice",
                        "--no-unwinding-assertions", "--generate-pytest-testcase", "--pytest-output-dir",
                        str(out_dir)], capture_output=True, text=True, timeout=timeout_seconds, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"status": "not_generated", "path": "", "reason": f"ESBMC did not finish: {type(exc).__name__}"}
    if not test.exists():
        return {"status": "not_generated", "path": "", "reason": "ESBMC wrote no test"}
    try:
        ast.parse(test.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        return {"status": "invalid", "path": str(test), "reason": f"ESBMC wrote invalid Python: {exc.msg}"}
    wrong_arity = _arity_problem(test.read_text(encoding="utf-8"), inline.func.id, len(inline.args))
    if wrong_arity:
        return {"status": "invalid", "path": str(test), "reason": wrong_arity}
    library = _cpython_source(rest)
    return _run_generated_test(test, module, library + "\n", exception)


def _ran(outcome: dict) -> bool:
    """The generated test was executed (a test that fails otherwise is "invalid" in ``pytest_reproducer``)."""
    return outcome["status"] in ("reproduces", "does_not_reproduce") or (
        outcome["status"] == "invalid"
        and not outcome["reason"].startswith(("ESBMC wrote invalid Python", ESBMC_WRONG_ARITY)))


def _verdict(outcome: dict) -> str:
    return "reproduces" if outcome["status"] == "reproduces" else "does_not_reproduce"


def esbmc_pytest(harness_path: Path, *, esbmc_command: list[str], bound: int, out_dir: Path, exception: str,
                 timeout_seconds: int = 120) -> dict:
    """ESBMC's own pytest for the harness's counterexample, run under CPython and kept only if it fails
    with ``exception``. Returns {"status", "path", "reason", "route"}: status is reproduces,
    does_not_reproduce or not_generated; route is direct (the harness's call rewritten with inline nondet
    inputs) or free_function (``pytest_reproducer``, after the direct route produced nothing usable)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    name = "bug_" + re.sub(r"\W", "_", Path(harness_path).parent.name or "harness")
    try:
        tree = ast.parse(Path(harness_path).read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError) as exc:
        return {"status": "not_generated", "path": "", "reason": f"harness unreadable: {type(exc).__name__}",
                "route": "direct"}
    direct = _direct_test(tree, name=name, esbmc_command=esbmc_command, bound=bound, out_dir=out_dir,
                          exception=exception, timeout_seconds=timeout_seconds)
    if _ran(direct):
        return {**direct, "status": _verdict(direct), "route": "direct"}
    fallback = _free_function(tree, name=name, esbmc_command=esbmc_command, bound=bound, out_dir=out_dir,
                              exception=exception, timeout_seconds=timeout_seconds)
    if _ran(fallback):
        return {**fallback, "status": _verdict(fallback), "route": "free_function"}
    reason = f"direct: {direct['reason']}; free function: {fallback['status']}, {fallback['reason']}"
    return {"status": "not_generated", "path": fallback["path"] or direct["path"], "reason": reason,
            "route": "free_function"}


def _free_function(tree: ast.Module, *, name: str, esbmc_command: list[str], bound: int, out_dir: Path,
                   exception: str, timeout_seconds: int) -> dict:
    found = _driver_call(tree)
    if found is None:
        return {"status": "not_generated", "path": "", "reason": "harness shape not recognised"}
    driver, _, inline = found
    function = ast.unparse(inline.func)
    definition = next((n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == function), None)
    params = {a.arg: ast.unparse(a.annotation) for a in definition.args.args if a.annotation} if definition else {}
    if definition is None or len(params) != len(definition.args.args):
        return {"status": "unsupported_shape", "path": "", "reason": "not a fully annotated free function"}
    rest = [n for n in tree.body if n is not driver and not (
        isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and getattr(n.value.func, "id", "") == driver.name)]
    source = _cpython_source(rest) + f"\n\n\ndef {DRIVER}() -> None:\n    pass\n"
    return pytest_reproducer(Program(source, 0, (), ()), function=function, params=params, exception=exception,
                             esbmc_command=esbmc_command, bound=bound, out_dir=out_dir, name=name,
                             timeout_seconds=timeout_seconds)


def pytest_seeds(path: str) -> dict[str, list]:
    """The values of a generated test's parametrize list, as the differential's seeds."""
    seeds: dict[str, list] = {}
    try:
        tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError, ValueError):
        return seeds
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and getattr(node.func, "attr", "") == "parametrize" and len(node.args) == 2:
            try:
                rows = ast.literal_eval(node.args[1])
            except ValueError:
                return seeds
            for row in rows:
                for value in row if isinstance(row, tuple) else (row,):
                    kind = "float" if isinstance(value, float) else "int" if isinstance(value, int) else None
                    if kind and value not in seeds.setdefault(kind, []):
                        seeds[kind].append(value)
    return seeds


_REPLAY_TEST = '''import json
import sys

sys.path.insert(0, {src!r})

from research_pipeline.verify.render import Program  # noqa: E402
from research_pipeline.verify.replay import concrete_replay  # noqa: E402

SOURCE = {source!r}
# JSON keeps NaN and infinities, which repr would write as bare names.
INPUTS = json.loads({inputs!r})


def test_{name}_raises_{exception}():
    program = Program(SOURCE, 0, {spans!r}, (), {target!r})
    verdict = concrete_replay(program, {function!r}, inputs=INPUTS)
    assert (verdict.status, verdict.exception_type) == ("reproduced", {exception!r}), verdict
'''


def replay_pytest(harness: str, function: str, replay: dict, *, spans: tuple, target: tuple) -> str | None:
    """A pytest that replays the harness with the replay's own inputs, through the same replay (so lists,
    NaN and ESBMC's names are rebuilt exactly), and expects the same exception at the suspect lines;
    None when the replay reproduced nothing to pin."""
    if replay.get("status") != "reproduced" or "inputs" not in replay or not replay.get("exception_type"):
        return None
    name = re.sub(r"\W", "_", function.rsplit(".", 1)[-1])
    return _REPLAY_TEST.format(src=str(Path(__file__).resolve().parents[2]), source=harness,
                               inputs=json.dumps(list(replay["inputs"])), name=name,
                               exception=replay["exception_type"], spans=tuple(spans), target=tuple(target),
                               function=function.rsplit(".", 1)[-1])


def run_replay_test(test: Path) -> dict:
    """Run a ``replay_pytest`` test where it was written; it passes exactly when the exception reproduces."""
    try:
        done = subprocess.run([*_no_network_prefix(), sys.executable, "-m", "pytest", "-q", "--tb=short",
                               "-p", "no:cacheprovider", test.name], cwd=test.parent, capture_output=True, text=True,
                              timeout=60, check=False,
                              env={key: os.environ[key] for key in ("PATH", "HOME") if key in os.environ})
        # No process_limits: the test starts the replay worker, which applies its own.
    except subprocess.TimeoutExpired:
        return {"status": "invalid", "path": str(test), "reason": "pytest timed out", "route": "replay"}
    tail = " ".join((done.stdout + done.stderr).strip().splitlines()[-2:])[:300]
    # pytest exits 1 when a test fails; anything else (2 to 5) means the test never ran.
    status = {0: "reproduces", 1: "does_not_reproduce"}.get(done.returncode, "invalid")
    return {"status": status, "path": str(test), "reason": tail, "route": "replay"}
