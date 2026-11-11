"""Pure checks and source preparation for agent-written harnesses."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass

from .astutil import locate, expression_nodes
from .hypothesis import BugHypothesis, VALUE_ORACLE
from .render import Program, RESULT_VAR, property_assert
from .replay import ReplayVerdict
from .source_replay import without_esbmc_imports

def property_line(harness: ast.Module, original: ast.Module, target: ast.FunctionDef, postcondition: str,
                  returns: str) -> int | str:
    """The line of the postcondition's assert in an agent's harness, or why the harness cannot check it.
    The agent writes the driver: the assert must be the engine's own, the only one added, and the value
    it reads must come straight from the call of the target."""
    if not postcondition:
        return "wrong-result hypothesis without a postcondition from the engine's spec"
    assertion = property_assert(postcondition)
    parsed = ast.parse(assertion).body[0]
    assert isinstance(parsed, ast.Assert)
    expected = ast.dump(parsed.test)
    real = {ast.dump(n.test) for n in ast.walk(original) if isinstance(n, ast.Assert)}
    asserts = [n for n in ast.walk(harness) if isinstance(n, ast.Assert)]
    found = [n for n in asserts if ast.dump(n.test) == expected]
    if len(found) != 1 or any(ast.dump(n.test) not in real for n in asserts if n is not found[0]):
        return f"harness.py must hold `{assertion}` once and no other assert of its own"
    stores = sum(isinstance(n, ast.Name) and n.id == RESULT_VAR and isinstance(n.ctx, ast.Store)
                 for n in ast.walk(harness))
    if returns == "None":
        return found[0].lineno if not stores else f"{RESULT_VAR} is assigned, but {target.name} returns None"
    calls = [n for n in ast.walk(harness) if isinstance(n, (ast.Assign, ast.AnnAssign))
             and [ast.unparse(t) for t in (n.targets if isinstance(n, ast.Assign) else [n.target])] == [RESULT_VAR]
             and isinstance(n.value, ast.Call) and target.name in (getattr(n.value.func, "id", None),
                                                                    getattr(n.value.func, "attr", None))
             and n.lineno < found[0].lineno]
    if stores != 1 or len(calls) != 1:
        return f"{RESULT_VAR} must be assigned once, before the assert, straight from a call of {target.name}"
    return found[0].lineno

def _definitions(tree: ast.Module) -> dict[str, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef]:
    """Every class and function by qualified name (``Class.method``)."""
    found: dict[str, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef] = {}
    def visit(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                found[prefix + child.name] = child
                visit(child, f"{prefix}{child.name}.")
    visit(tree, "")
    return found

def stub_cause(replay: ReplayVerdict, replayed: ast.Module | None, original: ast.Module) -> str:
    """Why the replayed exception belongs to code the agent invented, or "" when it does not."""
    if replayed is None:
        return ""
    real = set(_definitions(original))
    def spans(node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef, line: int | None) -> bool:
        return line is not None and node.lineno <= line <= (node.end_lineno or node.lineno)
    # The target may sit under a name the original lacks; whatever encloses the replayed line is not a stub.
    invented = {name: node for name, node in _definitions(replayed).items()
                if name not in real and not spans(node, replay.line)}
    if replay.raised_at is not None:
        inside = [name for name, node in invented.items() if spans(node, replay.raised_at)]
        if inside:
            return f"{replay.exception_type} raised inside the stub {max(inside, key=len)}"
    classes = {name for name, node in invented.items() if isinstance(node, ast.ClassDef) and "." not in name}
    named = classes & set(re.findall(r"\w+", replay.message))
    if named:
        return f"{replay.exception_type} names the stub class {min(named)}: {replay.message}"
    return ""

@dataclass(frozen=True)
class PreparedHarness:
    tree: ast.Module
    original_tree: ast.Module
    target: ast.FunctionDef | ast.AsyncFunctionDef
    spans: tuple[tuple[int, int], ...]
    program: Program


def prepare_harness(h: BugHypothesis, harness: str, original: str, postcondition: str = "",
                    returns: str = "") -> PreparedHarness | str:
    try:
        tree, original_tree = ast.parse(harness), ast.parse(original)
    except SyntaxError as exc:
        return f"harness does not parse: {exc.msg}"
    target = locate(tree, h.function, h.suspect_expression)
    if target is None:
        return f"target {h.function} missing from the harness"
    nodes = [node for node in expression_nodes(target, h.suspect_expression)
             if isinstance(node, (ast.expr, ast.stmt))]
    if not nodes:
        return "suspect expression missing from the harness target"
    spans = tuple(sorted({(n.lineno, n.end_lineno or n.lineno) for n in nodes}))
    line = 0
    if h.oracle == VALUE_ORACLE:
        found = property_line(tree, original_tree, target, postcondition, returns)
        if isinstance(found, str):
            return found
        line = found
    program = Program(without_esbmc_imports(harness), 0, spans, (),
                      (target.lineno, target.end_lineno or target.lineno), property_line=line)
    return PreparedHarness(tree, original_tree, target, spans, program)
