"""Self-healing: when a hypothesis stops before ESBMC reaches a verdict, the LLM patches the program with the
error and ESBMC's own documentation in front of it, and verification runs again.

A patch never touches the original file, only an in-memory copy of its source, and never the target
function's body (only annotations on its signature). Stubs the LLM writes return nondet values, so a
counterexample cannot come from a value the LLM picked; real code found through the call graph is copied as is.
"""

from __future__ import annotations

import ast
import difflib
import hashlib
import json
import threading
import re
import textwrap
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from ..scan.callgraph import CallGraph, FunctionNode
from .astutil import expression_nodes, find_function
from .esbmc_knowledge import (
    KNOWLEDGE_CACHE,
    KnowledgeIndex,
    esbmc_root_of,
    load_index,
    lookup,
)
from .hypothesis import BugHypothesis
from .lessons import (
    first_error,
    obstacle,
    read_notebook,
    teaches_repair,
)
from .loop import VerifyResult, verify_hypothesis
from .outcome import (
    CHECKED,
    ESBMC_ERROR,
    GROUNDING_FAILED,
    LLM_ONLY,
    MISSING_DEPENDENCY,
    UNSUPPORTED,
)
from .preservation import same_code

SYSTEM_PROMPT = (Path(__file__).resolve().parents[1] / "prompts" / "healing_prompt.txt").read_text(encoding="utf-8")
HEALABLE = frozenset({GROUNDING_FAILED, MISSING_DEPENDENCY, UNSUPPORTED})
# ESBMC-Python refusals with no rewrite that keeps the bug: repairing the harness only spends calls (PGENE601 11/11:
# the async entry point and numpy array parameter refusals). Other refusals have rewrites or annotations.
_NO_WORKAROUND = re.compile(r"async entry point|numpy array parameter is expected", re.I)


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


def _without_repeated_classes(added: str, source: str) -> str:
    """ESBMC keys a class by name alone and refuses two. A class the source already defines identically is dropped
    from ``added``, and of several definitions of one name in ``added`` only the last stays (as in Python)."""
    try:
        existing = {n.name: ast.dump(n) for n in ast.parse(source).body if isinstance(n, ast.ClassDef)}
        classes = [n for n in ast.parse(added).body if isinstance(n, ast.ClassDef)]
    except SyntaxError:
        return added
    last = {node.name: node for node in classes}
    lines = added.splitlines()
    for node in classes:
        if existing.get(node.name) == ast.dump(node) or last[node.name] is not node:
            for number in range(node.lineno - 1, node.end_lineno):
                lines[number] = ""
    return "\n".join(lines).strip("\n")


_STUB_NAME = re.compile(r"^_\w*Stub\w*$")


def _without_replaced_stubs(source: str, added: str) -> str:
    """A stub class an earlier repair wrote and this one writes again under the same name, differently: the
    newer one replaces it. Only ``_...Stub`` names, so a class of the project is never removed."""
    try:
        redefined = {n.name for n in ast.parse(added).body if isinstance(n, ast.ClassDef) and _STUB_NAME.match(n.name)}
        old = [n for n in ast.parse(source).body if isinstance(n, ast.ClassDef) and n.name in redefined]
    except SyntaxError:
        return source
    lines = source.splitlines()
    for node in old:
        for number in range(node.lineno - 1, node.end_lineno):
            lines[number] = ""
    return "\n".join(lines) + "\n"


def _without_replaced_functions(source: str, definitions: str) -> str:
    """The stubs are inserted near the top, so the real function of the same name, defined later, would win
    (Python keeps the last definition) and the stub never runs: a stub of a callee replaces it instead.
    ``patch_problems`` already refuses a patch that changes the target function."""
    try:
        stubbed = {n.name for n in ast.parse(definitions).body if isinstance(n, ast.FunctionDef)}
        old = [n for n in ast.parse(source).body if isinstance(n, ast.FunctionDef) and n.name in stubbed]
    except SyntaxError:
        return source
    lines = source.splitlines()
    for node in old:
        for number in range(min([node.lineno, *(d.lineno for d in node.decorator_list)]) - 1, node.end_lineno):
            lines[number] = ""
    return "\n".join(lines) + "\n"


def apply_patch(source: str, patch: Patch) -> str:
    for old, new in patch.edits:
        count = source.count(old)
        if count != 1:
            raise PatchError(f"edit text not found: {old[:60]!r}" if count == 0
                             else f"edit text appears {count} times: {old[:60]!r}")
        source = source.replace(old, new)
    added = _without_repeated_classes("\n\n".join(p.strip("\n") for p in (patch.real_code, patch.definitions)
                                                    if p.strip()), source)
    if not added.strip():
        return source
    source = _without_replaced_stubs(source, added)
    if patch.definitions.strip():
        source = _without_replaced_functions(source, patch.definitions)
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


def patch_problems(original: str, patch: Patch, function: str, expression: str = "") -> list[str]:
    """With ``expression``, the target's body may be simplified as long as the suspect stays in it: the replay
    then runs the original body (``verify_with_healing``), so a simplification that matters fails to confirm."""
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
    if old is not None and (new is None or not same_code(old, new, before, after)):
        if not expression:
            problems.append(f"the body of the target function {function!r} changed")
        elif new is None or not expression_nodes(new, expression):
            problems.append(f"the body change drops the suspect expression of {function!r}")
    return problems


def body_edits(source: str, edits: tuple[tuple[str, str], ...], function: str) -> tuple[tuple[str, str], ...]:
    """The edits whose text lies inside the target function."""
    try:
        node = find_function(ast.parse(source), function)
    except SyntaxError:
        return ()
    segment = ast.get_source_segment(source, node) if node is not None else None
    return tuple(e for e in edits if segment and e[0] in segment) if segment else ()


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


_QUOTED = re.compile(r"'([A-Za-z_][\w.]*)'|\.(\w+)\(")


def _error_lines(source: str, reason: str, limit: int = 8) -> str:
    """Source lines that name an identifier ESBMC's message quotes, with line numbers: an error often points at a
    class attribute or a callee outside the target function, which the repair prompt would not otherwise show."""
    names = {part for match in _QUOTED.findall(reason) for part in match if part}
    names = {n.split(".")[-1] for n in names} - {"main", "self"}
    found = [f"{number}: {line.rstrip()}" for number, line in enumerate(source.splitlines(), 1)
             if any(re.search(rf"\b{re.escape(n)}\b", line) for n in names)]
    return "\n".join(found[:limit])


def _near_lines(source: str, text: str, count: int = 3) -> list[str]:
    """The lines of ``source`` closest to a quoted edit text that was not found."""
    first = text.strip().splitlines()[0] if text.strip() else ""
    lines = [line.rstrip() for line in source.splitlines() if line.strip()]
    return difflib.get_close_matches(first, lines, n=count, cutoff=0.4)


def _function_code(source: str, tree: ast.Module, qualified: str) -> str:
    function = find_function(tree, qualified)
    return ast.get_source_segment(source, function) or "" if function is not None else ""


def _lesson_fix(patch: dict) -> str:
    lines = [line for old, new in patch.get("edits") or ()
             for line in [*(f"-{x}" for x in old.splitlines()), *(f"+{x}" for x in new.splitlines())]]
    return "\n".join([*lines, *(f"+{x}" for x in str(patch.get("definitions") or "").splitlines())])


_REFUSED = frozenset({MISSING_DEPENDENCY, UNSUPPORTED})


def learned_repairs(log: list[dict]) -> list[tuple[dict, str]]:
    """The rounds whose patch made ESBMC reach a verdict on a program it refused, with the patch as a diff.
    Left out: a simplified target body, and patches without edits or stubs (a grounding repair moves the
    hypothesis; code copied from the repository is no rewrite to learn)."""
    found = []
    for entry in log:
        fix = _lesson_fix(entry.get("patch") or {})
        if (entry.get("verdict_before") in _REFUSED and entry.get("verdict_after") in CHECKED
                and not entry.get("simplified_body") and fix):
            found.append((entry, fix))
    return found


class Healer:
    """Proposes one patch per call; the caller validates it with ``patch_problems`` and verifies again."""

    def __init__(self, llm, knowledge: KnowledgeIndex | None, graph: CallGraph | None = None,
                 lessons: str | None = None, *, auto_lessons: bool = False, run_dir: Path | None = None):
        """``lessons`` are approved repairs; ``auto_lessons`` queues candidates under ``run_dir``."""
        self.llm, self.knowledge, self.graph = llm, knowledge, graph
        self.auto_lessons, self.run_dir = auto_lessons and lessons is None, run_dir
        self._learn_lock = threading.Lock()
        if lessons is None:
            self.lessons, self.lessons_version = read_notebook()
        else:
            self.lessons = lessons.strip()
            self.lessons_version = hashlib.sha256(self.lessons.encode("utf-8")).hexdigest()[:12]

    def refresh(self) -> str:
        """Reload approved repairs when automatic proposal collection is enabled."""
        if self.auto_lessons:
            self.lessons, self.lessons_version = read_notebook()
        return self.lessons_version

    @property
    def config_label(self) -> str:
        """The heal mode and the notebook version (the hash the agent arm records), for a scan's resume fingerprint.
        The quarantine mode and approved notebook version enter the resume fingerprint."""
        mode = "error+kb" if self.knowledge is not None else "error"
        if self.auto_lessons:
            return f"{mode}+notes:quarantine-v1:{self.lessons_version}"
        return f"{mode}+notes:{self.lessons_version}" if self.lessons else mode

    def learn(self, h: BugHypothesis, log: list[dict], result: dict) -> int:
        """Queue candidate repairs for the gate; return how many were new."""
        if not self.auto_lessons or not teaches_repair(result):
            return 0
        program = result.get("_learning_program", "")
        if not self.run_dir or not isinstance(program, str) or not program.strip():
            return 0
        from research_pipeline.maintenance.learning import queue_lesson

        with self._learn_lock:
            return sum(queue_lesson(error=first_error(entry["reason_before"]), fix=fix, program=program,
                                    case=h.hypothesis_id, run_dir=self.run_dir)
                       for entry, fix in learned_repairs(log)
                       if first_error(entry["reason_before"]).startswith("ERROR:"))

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

    def _ask(self, task: str, previous: list[dict], source: str = "") -> dict | None:
        if previous:
            task += "\n\nEarlier repairs were rejected:\n" + "\n".join(
                f"- {'; '.join(p.get('problems') or [p.get('verdict_after', '')])}" for p in previous)
            for problem in (q for p in previous for q in p.get("problems") or ()):
                match = re.match(r"edit text not found: ('.*'|\".*\")$", problem)
                if match and source:
                    near = _near_lines(source, ast.literal_eval(match.group(1)))
                    if near:
                        task += "\nThe closest lines in the file are:\n" + "\n".join(near)
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
        around = _error_lines(source, reason)
        if around:
            task += f"Lines of the file that name what ESBMC mentions (copy edit text from here exactly):\n{around}\n"
        if names:
            task += f"Names to stub: {', '.join(sorted(names))}. How the file uses them:\n{_usage_lines(source, names)}\n"
        if self.lessons:
            task += f"\nRepairs learned on earlier cases (approved by the researcher or added automatically):\n{self.lessons}\n"
        if knowledge:
            task += f"\nESBMC-Python documentation and examples it accepts:\n{knowledge}\n"
        task += '\nGive "edits" and/or "definitions".'
        data = self._ask(task, previous, source)
        if not data:
            return None
        edits = tuple((str(e.get("old", "")), str(e.get("new", ""))) for e in data.get("edits") or []
                      if isinstance(e, dict) and e.get("old"))
        definitions = str(data.get("definitions") or "")
        if not edits and not definitions.strip():
            return None
        return Patch(edits=edits, definitions=definitions)


# Crashes and solver failures inside ESBMC say nothing about the harness: reported as tool bugs, not repaired.
_INTERNAL = re.compile(r"vector::_M_range_check|json\.exception|irep2_cast_error|Segmentation fault|terminate called"
                       r"|bad optional access|Z3 error|Incompatible struct in cast-to-struct|std::\w+")


def verify_with_healing(h: BugHypothesis, *, healer: Healer | None, source: str, rounds: int = 3,
                        spec_llm_after_heal=None, triage: bool = False, **verify_kwargs) -> VerifyResult:
    """``verify_hypothesis`` plus up to ``rounds`` repairs per obstacle, while the verdict is one ESBMC never
    reached; a new ESBMC message is progress and gets its own rounds (at most ``3 * rounds`` in all).
    The result keeps the original hypothesis, which is what the metric scores."""
    result = verify_hypothesis(h, source=source, **verify_kwargs)
    if healer is None or (result.verdict == UNSUPPORTED and (triage or _NO_WORKAROUND.search(result.reason))):
        return result
    version = healer.refresh()
    log: list[dict] = []
    current, text, replay_text = h, source, source
    spent: dict[str, int] = {}
    for number in range(3 * rounds):
        if result.verdict not in HEALABLE:
            break
        if _INTERNAL.search(result.reason):
            result.reason, result.verdict = f"internal ESBMC error (tool bug): {result.reason}", ESBMC_ERROR
            break
        seen = obstacle(result.reason)
        if spent.get(seen, 0) >= rounds:
            break
        spent[seen] = spent.get(seen, 0) + 1
        entry = {"round": number, "verdict_before": result.verdict, "reason_before": result.reason[:500]}
        log.append(entry)
        patch = healer.propose(current, text, result.verdict, result.reason, log[:-1])
        if patch is None:
            entry["problems"] = ["no usable repair"]
            continue
        problems = patch_problems(text, patch, current.function, current.suspect_expression)
        entry["patch"] = asdict(patch)
        if problems:
            entry["problems"] = problems
            continue
        simplified = body_edits(text, patch.edits, current.function)
        entry["simplified_body"] = bool(simplified)
        text = apply_patch(text, patch)
        replay_text = apply_patch(replay_text, replace(patch, edits=tuple(e for e in patch.edits if e not in simplified)))
        if patch.hypothesis_function:
            current = replace(current, function=patch.hypothesis_function,
                              suspect_expression=patch.hypothesis_expression or current.suspect_expression)
            entry["hypothesis_after"] = current.to_dict()
        if spec_llm_after_heal is not None:
            verify_kwargs = {**verify_kwargs, "llm": spec_llm_after_heal}
        result = verify_hypothesis(current, source=text, replay_source=replay_text if replay_text != text else None,
                                   **verify_kwargs)
        entry["verdict_after"] = result.verdict
    if result.verdict in HEALABLE:
        result.reason, result.verdict = f"{result.verdict}: {result.reason}", LLM_ONLY
    result.hypothesis, result.healing, result.notebook_version = h, log, version
    try:
        healer.learn(h, log, {**result.to_dict(), "_learning_program": source})
    except (OSError, ValueError) as exc:
        log.append({"learning_error": f"{type(exc).__name__}: {exc}"})
    return result


HEAL_MODES = ("none", "error", "error+kb")


def build_healer(mode: str, *, llm, esbmc_command: list[str] | None, graph: CallGraph | None = None,
                 cache_dir: Path = KNOWLEDGE_CACHE, auto_lessons: bool = False,
                 run_dir: Path | None = None) -> Healer | None:
    """``error``: the LLM sees ESBMC's message only; ``error+kb``: also the checkout's README and tests."""
    if mode not in HEAL_MODES:
        raise ValueError(f"heal mode must be one of {HEAL_MODES}")
    if mode == "none":
        return None
    knowledge = None
    if mode == "error+kb":
        root = esbmc_root_of(esbmc_command or ["esbmc"])
        knowledge = load_index(root, cache_dir) if root is not None else KnowledgeIndex("")
    return Healer(llm, knowledge, graph, auto_lessons=auto_lessons, run_dir=run_dir)
