"""Self-healing: when a hypothesis stops before ESBMC reaches a verdict, the LLM patches the program with the
error and ESBMC's own documentation in front of it, and verification runs again.

A patch never touches the original file, only an in-memory copy of its source, and never the target
function's body (only annotations on its signature). Stubs the LLM writes return nondet values, so a
counterexample cannot come from a value the LLM picked; real code found through the call graph is copied as is.
"""

from __future__ import annotations

import ast
import difflib
import json
import re
import textwrap
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ..scan.callgraph import CallGraph, FunctionNode
from .astutil import body_signature, expression_nodes, find_function
from .esbmc_knowledge import (
    KNOWLEDGE_CACHE,
    KnowledgeIndex,
    esbmc_root_of,
    load_index,
    lookup,
)
from .hypothesis import BugHypothesis
from .loop import VerifyResult, verify_hypothesis
from .outcome import GROUNDING_FAILED, LLM_ONLY, MISSING_DEPENDENCY, UNSUPPORTED

SYSTEM_PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "healing_prompt.txt").read_text(encoding="utf-8")
HEALABLE = frozenset({GROUNDING_FAILED, MISSING_DEPENDENCY, UNSUPPORTED})


class PatchError(ValueError):
    pass


@dataclass(frozen=True)
class Patch:
    edits: tuple[tuple[str, str], ...] = ()
    definitions: str = ""  # stubs written by the LLM, checked by stub_problems
    real_code: str = ""  # definitions copied from the repository through the call graph
    hypothesis_function: str = ""  # grounding repair: where the hypothesis really is
    hypothesis_expression: str = ""


def _insert_point(lines: list[str], tree: ast.Module) -> int:
    imports = [n.end_lineno or n.lineno for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    return max(imports, default=0)


def apply_patch(source: str, patch: Patch) -> str:
    for old, new in patch.edits:
        count = source.count(old)
        if count != 1:
            raise PatchError(f"edit text not found: {old[:60]!r}" if count == 0
                             else f"edit text appears {count} times: {old[:60]!r}")
        source = source.replace(old, new)
    added = "\n\n".join(p.strip("\n") for p in (patch.real_code, patch.definitions) if p.strip())
    if not added:
        return source
    lines = source.splitlines()
    try:
        at = _insert_point(lines, ast.parse(source))
    except SyntaxError:
        at = 0
    return "\n".join([*lines[:at], "", "", added, "", "", *lines[at:]]) + "\n"


def _nondet_call(node: ast.expr | None, classes: set[str]) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and (node.func.id.startswith("nondet_") or node.func.id in classes))


def _returns_none(function: ast.FunctionDef) -> bool:
    return isinstance(function.returns, ast.Constant) and function.returns.value is None


def stub_problems(definitions: str) -> list[str]:
    """A stub returns nondet values (or None from ``-> None``), sets attributes to them, and never raises."""
    try:
        tree = ast.parse(definitions)
    except SyntaxError:
        return ["the stubs do not parse"]
    classes = {n.name for n in tree.body if isinstance(n, ast.ClassDef)}
    problems = []
    for function in (n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)):
        for node in ast.walk(function):
            if isinstance(node, (ast.Raise, ast.Assert)):
                problems.append(f"stub {function.name!r} raises or asserts")
            elif isinstance(node, ast.Return):
                none = node.value is None or (isinstance(node.value, ast.Constant) and node.value.value is None)
                if not (_nondet_call(node.value, classes) or (none and _returns_none(function))):
                    problems.append(f"stub {function.name!r} returns a fixed value; return nondet_*() instead")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)) and function.name == "__init__":
                if not _nondet_call(node.value, classes):
                    problems.append(f"stub class field in {function.name!r} has a fixed value; use nondet_*()")
    return sorted(set(problems))


def patch_problems(original: str, patch: Patch, function: str) -> list[str]:
    try:
        patched = apply_patch(original, patch)
    except PatchError as exc:
        return [str(exc)]
    try:
        before, after = ast.parse(original), ast.parse(patched)
    except SyntaxError:
        return ["the patched source does not parse"]
    problems = stub_problems(patch.definitions) if patch.definitions.strip() else []
    old, new = find_function(before, function), find_function(after, function)
    if old is not None and (new is None or body_signature(old) != body_signature(new)):
        problems.append(f"the body of the target function {function!r} changed")
    return problems


def _source_of(graph: CallGraph, node: FunctionNode) -> str:
    lines = (graph.root / node.file).read_text(encoding="utf-8", errors="replace").splitlines()
    return "\n".join(lines[node.start_line - 1:node.end_line])


def _module_functions(graph: CallGraph, name: str) -> list[FunctionNode]:
    return [f for f in graph.functions.values() if f.qualname == name and f.top_level and not f.nested]


def _called_names(code: str) -> set[str]:
    try:
        tree = ast.parse(textwrap.dedent(code))
    except SyntaxError:
        return set()
    return {n.func.id for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}


def graph_definitions(names: set[str], graph: CallGraph, depth: int = 2, max_chars: int = 20000) -> str:
    """The repository's own code of ``names`` and of what it calls, ``depth`` levels down; a name defined
    more than once is left out (the LLM stubs it instead)."""
    found: dict[str, str] = {}
    frontier = set(names)
    for _ in range(depth):
        nxt: set[str] = set()
        for name in sorted(frontier - set(found)):
            matches = _module_functions(graph, name)
            if len(matches) == 1:
                found[name] = _source_of(graph, matches[0])
                nxt |= _called_names(found[name])
        frontier = nxt
    code = "\n\n\n".join(found.values())
    return code if len(code) <= max_chars else ""


_NAME_PATTERNS = (r"undefined name\(s\): ([\w, .]+)", r'Object "(\w+)" not found', r"name '(\w+)' is not defined",
                  r"Variable '?(\w+)'? (?:is )?not (?:defined|found)")


def missing_names(reason: str) -> set[str]:
    names: set[str] = set()
    for pattern in _NAME_PATTERNS:
        for match in re.finditer(pattern, reason):
            names |= {n.strip() for n in match.group(1).split(",") if n.strip()}
    return names


def _qualified_functions(tree: ast.Module) -> list[str]:
    found = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            found.append(node.name)
        elif isinstance(node, ast.ClassDef):
            found += [f"{node.name}.{m.name}" for m in node.body if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return found


def _usage_lines(source: str, names: set[str], limit: int = 12) -> str:
    lines = [line.strip() for line in source.splitlines() if any(re.search(rf"\b{re.escape(n)}\b", line) for n in names)]
    return "\n".join(lines[:limit])


def _function_code(source: str, tree: ast.Module, qualified: str) -> str:
    function = find_function(tree, qualified)
    return ast.get_source_segment(source, function) or "" if function is not None else ""


class Healer:
    """Proposes one patch per call; the caller validates it with ``patch_problems`` and verifies again."""

    def __init__(self, llm, knowledge: KnowledgeIndex | None, graph: CallGraph | None = None):
        self.llm, self.knowledge, self.graph = llm, knowledge, graph

    def propose(self, h: BugHypothesis, source: str, verdict: str, reason: str, previous: list[dict]) -> Patch | None:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return None
        if verdict == GROUNDING_FAILED:
            return self._grounding(h, source, tree, reason, previous)
        names = missing_names(reason)
        if names and self.graph is not None:
            real = graph_definitions(names, self.graph)
            defined = {n for n in names if re.search(rf"^def {re.escape(n)}\b", real, re.MULTILINE)}
            if real and defined == names:
                return Patch(real_code=real)
        return self._repair(h, source, tree, verdict, reason, names, previous)

    def _ask(self, task: str, previous: list[dict]) -> dict | None:
        if previous:
            task += "\n\nEarlier repairs were rejected:\n" + "\n".join(
                f"- {'; '.join(p.get('problems') or [p.get('verdict_after', '')])}" for p in previous)
        reply = self.llm.complete(SYSTEM_PROMPT, task, json_mode=True)
        try:
            data = json.loads(reply.harness)
        except (json.JSONDecodeError, TypeError):
            return None
        return data if isinstance(data, dict) else None

    def _grounding(self, h, source, tree, reason, previous) -> Patch | None:
        functions = _qualified_functions(tree)
        closest = difflib.get_close_matches(h.function, functions, n=1, cutoff=0) or [""]
        task = (f"Task: grounding. The hypothesis names a function or expression the file does not have ({reason}).\n"
                f"Hypothesis: function {h.function!r}, suspect expression {h.suspect_expression!r}, "
                f"trigger: {h.trigger_condition}\nFunctions in the file: {', '.join(functions)}\n"
                f"Closest function's code:\n```python\n{_function_code(source, tree, closest[0])}\n```\n"
                'Give "function" and "expression" for the same suspicion, copied from the code.')
        data = self._ask(task, previous)
        if not data:
            return None
        function, expression = str(data.get("function", "")), str(data.get("expression", ""))
        node = find_function(tree, function)
        if node is None or not expression or not expression_nodes(node, expression):
            return None
        return Patch(hypothesis_function=function, hypothesis_expression=expression)

    def _repair(self, h, source, tree, verdict, reason, names, previous) -> Patch | None:
        code = _function_code(source, tree, h.function)
        knowledge = lookup(self.knowledge, reason, code) if self.knowledge else ""
        task = (f"Task: ESBMC could not check the program ({verdict}).\nESBMC said:\n{reason[:1500]}\n"
                f"Target function {h.function!r}, suspect expression {h.suspect_expression!r}, "
                f"trigger: {h.trigger_condition}\nTarget code:\n```python\n{code}\n```\n")
        if names:
            task += f"Names to stub: {', '.join(sorted(names))}. How the file uses them:\n{_usage_lines(source, names)}\n"
        if knowledge:
            task += f"\nESBMC-Python documentation and examples it accepts:\n{knowledge}\n"
        task += '\nGive "edits" and/or "definitions".'
        data = self._ask(task, previous)
        if not data:
            return None
        edits = tuple((str(e.get("old", "")), str(e.get("new", ""))) for e in data.get("edits") or []
                      if isinstance(e, dict) and e.get("old"))
        definitions = str(data.get("definitions") or "")
        if not edits and not definitions.strip():
            return None
        return Patch(edits=edits, definitions=definitions)


def verify_with_healing(h: BugHypothesis, *, healer: Healer | None, source: str, rounds: int = 3,
                        spec_llm_after_heal=None, **verify_kwargs) -> VerifyResult:
    """``verify_hypothesis`` plus up to ``rounds`` repairs while the verdict is one ESBMC never reached.
    The result keeps the original hypothesis, which is what the metric scores."""
    result = verify_hypothesis(h, source=source, **verify_kwargs)
    if healer is None:
        return result
    log: list[dict] = []
    current, text = h, source
    for number in range(rounds):
        if result.verdict not in HEALABLE:
            break
        entry = {"round": number, "verdict_before": result.verdict, "reason_before": result.reason[:500]}
        log.append(entry)
        patch = healer.propose(current, text, result.verdict, result.reason, log[:-1])
        if patch is None:
            entry["problems"] = ["no usable repair"]
            continue
        problems = patch_problems(text, patch, current.function)
        entry["patch"] = asdict(patch)
        if problems:
            entry["problems"] = problems
            continue
        text = apply_patch(text, patch)
        if patch.hypothesis_function:
            current = replace(current, function=patch.hypothesis_function,
                              suspect_expression=patch.hypothesis_expression or current.suspect_expression)
            entry["hypothesis_after"] = current.to_dict()
        if spec_llm_after_heal is not None:
            verify_kwargs = {**verify_kwargs, "llm": spec_llm_after_heal}
        result = verify_hypothesis(current, source=text, **verify_kwargs)
        entry["verdict_after"] = result.verdict
    if result.verdict in HEALABLE:
        result.reason, result.verdict = f"{result.verdict}: {result.reason}", LLM_ONLY
    result.hypothesis, result.healing = h, log
    return result


HEAL_MODES = ("none", "error", "error+kb")


def build_healer(mode: str, *, llm, esbmc_command: list[str] | None, graph: CallGraph | None = None,
                 cache_dir: Path = KNOWLEDGE_CACHE) -> Healer | None:
    """``error``: the LLM sees ESBMC's message only; ``error+kb``: also the checkout's README and tests."""
    if mode not in HEAL_MODES:
        raise ValueError(f"heal mode must be one of {HEAL_MODES}")
    if mode == "none":
        return None
    knowledge = None
    if mode == "error+kb":
        root = esbmc_root_of(esbmc_command or ["esbmc"])
        knowledge = load_index(root, cache_dir) if root is not None else KnowledgeIndex("")
    return Healer(llm, knowledge, graph)
