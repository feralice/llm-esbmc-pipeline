"""What the code around a target says about its inputs: call sites, literal arguments and in-function use.

Everything here is read from the AST, never guessed. The spec prompt shows it as evidence, and
``usage_problems`` rejects a spec type that the function's own use of the input contradicts."""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from ..scan.callgraph import CallGraph, CallSite, _shorten, build_source_callgraph
from ..scan.context import NO_CALLERS, caller_context
from .astutil import find_function
from .grounding import Grounded
from .hypothesis import BugHypothesis
from .spec import OBJECT, InputSpec, input_types, member_types, parse_type

MAX_SITES = 5
MAX_CALLER_CHARS = 2_000
MAX_REFERENCES = 3
MAX_LINE_CHARS = 160
MAX_FACT_CHARS = 1_200
# Lives in the block, not the system prompt, so the spec_context="none" baseline keeps the old prompt.
EVIDENCE_RULE = ("These call sites and facts are evidence: give each input a type that agrees with what the "
                 "callers pass and with how the function uses it. An input whose methods are called, or that "
                 "is subscripted or iterated, cannot be int, float or bool; a spec that contradicts that use "
                 "is rejected.")
# An input handed to one of these may hold several types; the harness picks one, so usage proves nothing.
_TYPE_TESTS = frozenset({"isinstance", "hasattr", "getattr", "type", "callable"})
_LITERALS = {ast.JoinedStr: "str", ast.List: "list", ast.ListComp: "list", ast.Tuple: "tuple", ast.Dict: "dict",
             ast.DictComp: "dict", ast.Set: "set", ast.SetComp: "set", ast.Lambda: "function"}
_MEMBERS = {kind: frozenset(dir(value)) for kind, value in {
    "int": int, "float": float, "bool": bool, "str": str, "bytes": bytes, "list": list, "tuple": tuple,
    "dict": dict, "set": set, "frozenset": frozenset, "none": None}.items()}
_NOT_SUBSCRIPTABLE = frozenset({"int", "float", "bool", "none", "set", "frozenset"})
_NOT_ITERABLE = frozenset({"int", "float", "bool", "none"})


@dataclass(frozen=True)
class Usage:
    subscripted: bool = False
    iterated: bool = False
    sized: bool = False


@dataclass(frozen=True)
class CallerFacts:
    sites: str = ""  # caller_context text; "" when no call site was found
    site_count: int = 0
    references: tuple[str, ...] = ()  # "  845 | line" where the function is passed as a value
    defaults: dict[str, str] = field(default_factory=dict)  # param -> literal type of its default
    passed: dict[str, dict[str, int]] = field(default_factory=dict)  # param -> literal type -> call sites
    usage: dict[str, Usage] = field(default_factory=dict)  # "param" or "self.attr"
    unchecked: frozenset[str] = frozenset()  # inputs rebound, shadowed or type-tested in the function


def literal_type(node: ast.expr) -> str | None:
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
        node = node.operand
        if not (isinstance(node, ast.Constant) and type(node.value) in (int, float)):
            return None
    if isinstance(node, ast.Constant):
        return "None" if node.value is None else type(node.value).__name__
    return _LITERALS.get(type(node))


def function_key(graph: CallGraph, file: str, qualname: str) -> str | None:
    """The graph key of ``qualname`` in ``file``; None when absent or defined more than once."""
    path = Path(file)
    try:
        relative = path.resolve().relative_to(graph.root).as_posix()
    except ValueError:
        relative = path.name
    found = [f for f in graph.functions.values() if f.qualname == qualname and f.file in (relative, path.name)]
    return found[0].key if len(found) == 1 and not found[0].ambiguous else None


def _input_key(node: ast.AST, params: set[str], attrs: set[str]) -> str | None:
    if isinstance(node, ast.Name) and node.id in params:
        return node.id
    if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "self"
            and node.attr in attrs):
        return f"self.{node.attr}"
    return None


def _usage(function: ast.FunctionDef, params: set[str], attrs: set[str]) -> tuple[dict[str, Usage], frozenset[str]]:
    flags: dict[str, set[str]] = {}
    unchecked: set[str] = set()
    for node in ast.walk(function):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)) and node is not function:
            unchecked |= {a.arg for a in ast.walk(node.args) if isinstance(a, ast.arg) and a.arg in params}
        elif isinstance(node, (ast.Name, ast.Attribute)) and isinstance(node.ctx, (ast.Store, ast.Del)):
            key = _input_key(node, params, attrs)
            if key:
                unchecked.add(key)
        elif isinstance(node, ast.Subscript):
            key = _input_key(node.value, params, attrs)
            if key:
                flags.setdefault(key, set()).add("subscripted")
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            key = _input_key(node.iter, params, attrs)
            if key:
                flags.setdefault(key, set()).add("iterated")
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            keys = [key for arg in node.args if (key := _input_key(arg, params, attrs))]
            if node.func.id in _TYPE_TESTS:
                unchecked.update(keys)
            elif node.func.id == "len":
                for key in keys:
                    flags.setdefault(key, set()).add("sized")
    usage = {key: Usage("subscripted" in f, "iterated" in f, "sized" in f)
             for key, f in flags.items() if key not in unchecked}
    return usage, frozenset(unchecked)


def _defaults(function: ast.FunctionDef, params: set[str]) -> dict[str, str]:
    args = function.args
    positional = [*args.posonlyargs, *args.args]
    pairs = list(zip(positional[len(positional) - len(args.defaults):], args.defaults))
    pairs += [(a, d) for a, d in zip(args.kwonlyargs, args.kw_defaults) if d is not None]
    return {a.arg: kind for a, d in pairs if a.arg in params and (kind := literal_type(d))}


def _call_at(tree: ast.Module, site: CallSite) -> ast.Call | None:
    return next((n for n in ast.walk(tree) if isinstance(n, ast.Call) and n.lineno == site.line
                 and (n.end_lineno or n.lineno) == site.end_line and _shorten(ast.unparse(n.func)) == site.expression),
                None)


def _passed(graph: CallGraph, sites: list[CallSite], grounded: Grounded) -> dict[str, dict[str, int]]:
    positional = [p.name for p in grounded.params if not p.keyword]
    names = {p.name for p in grounded.params}
    trees: dict[str, ast.Module] = {}
    passed: dict[str, dict[str, int]] = {}
    for site in sites:
        if site.file not in trees:
            try:
                trees[site.file] = ast.parse("\n".join(graph.sources.get(site.file, [])))
            except (SyntaxError, ValueError, RecursionError):
                trees[site.file] = ast.Module(body=[], type_ignores=[])
        call = _call_at(trees[site.file], site)
        if call is None:
            continue
        # ``Class.method(obj, x)`` passes the receiver first: positions do not line up with the parameters.
        unbound = (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
                   and call.func.value.id == grounded.class_name and grounded.entry == "method")
        bound: list[tuple[str, ast.expr]] = []
        if not unbound:
            for name, arg in zip(positional, call.args):
                if isinstance(arg, ast.Starred):
                    break
                bound.append((name, arg))
        bound += [(k.arg, k.value) for k in call.keywords if k.arg in names]
        for name, value in bound:
            kind = literal_type(value)
            if kind:
                counts = passed.setdefault(name, {})
                counts[kind] = counts.get(kind, 0) + 1
    return passed


def _references(tree: ast.Module, lines: list[str], grounded: Grounded, name: str) -> tuple[str, ...]:
    """Lines where the target is used as a value (``partial(f, ...)``, a callback), not called."""
    called = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    found = set()
    for node in ast.walk(tree):
        if id(node) in called or not isinstance(getattr(node, "ctx", None), ast.Load):
            continue
        if grounded.class_name is None:
            hit = isinstance(node, ast.Name) and node.id == name
        else:
            hit = (isinstance(node, ast.Attribute) and node.attr == name and isinstance(node.value, ast.Name)
                   and node.value.id in ("self", "cls", grounded.class_name))
        if hit:
            found.add(node.lineno)
    return tuple(f"{n:>5} | {lines[n - 1].strip()[:MAX_LINE_CHARS]}" for n in sorted(found)[:MAX_REFERENCES])


def collect_facts(h: BugHypothesis, grounded: Grounded, source: str, *, graph: CallGraph | None = None) -> CallerFacts:
    """``source`` is the verification file; ``graph`` the repository's (scan mode), else that file alone."""
    try:
        tree = ast.parse(source)
        if graph is None:
            graph = build_source_callgraph(source, Path(h.file).name)
    except (SyntaxError, ValueError, RecursionError):
        return CallerFacts()
    params = {p.name for p in grounded.params}
    function = find_function(tree, h.function)
    usage, unchecked = (_usage(function, params, set(grounded.receiver_attrs)) if function is not None
                        else ({}, frozenset()))
    key = function_key(graph, h.file, h.function)
    sites = graph.callers(key) if key else []
    text = caller_context(graph, key, max_sites=MAX_SITES, max_chars=MAX_CALLER_CHARS, rename=False) if key else ""
    return CallerFacts(
        sites="" if text == NO_CALLERS else text,
        site_count=len(sites),
        references=_references(tree, source.splitlines(), grounded, h.function.split(".")[-1]),
        defaults=_defaults(function, params) if function is not None else {},
        passed=_passed(graph, sites, grounded),
        usage=usage,
        unchecked=unchecked,
    )


def _fact_line(key: str, facts: CallerFacts) -> str:
    bits = []
    if key in facts.defaults:
        bits.append(f"default is {facts.defaults[key]}")
    if key in facts.passed:
        bits.append("callers pass " + ", ".join(f"{kind} ({n}x)" for kind, n in sorted(facts.passed[key].items())))
    use = facts.usage.get(key)
    if use:
        bits += [label for flag, label in ((use.subscripted, "subscripted"), (use.iterated, "iterated"),
                                           (use.sized, "passed to len()")) if flag]
    return f"- {key}: " + "; ".join(bits) if bits else ""


def render_section(facts: CallerFacts, grounded: Grounded) -> str:
    """The spec prompt's evidence block; bounded by MAX_CALLER_CHARS, MAX_REFERENCES and MAX_FACT_CHARS."""
    parts = ["Call sites (real code that calls this function, verbatim; evidence for the types callers pass):\n"
             "```python\n" + (facts.sites or "# none found in the verification source") + "\n```"]
    if facts.references:
        parts.append("The function is also used as a value here:\n```python\n" + "\n".join(facts.references) + "\n```")
    keys = [p.name for p in grounded.params] + [f"self.{a}" for a in grounded.receiver_attrs]
    lines = [line for key in keys if (line := _fact_line(key, facts))]
    if lines:
        text = "\n".join(lines)
        if len(text) > MAX_FACT_CHARS:
            text = text[:MAX_FACT_CHARS] + "\n[...]"
        parts.append("Facts read from the code (computed, not guessed):\n" + text)
    parts.append(EVIDENCE_RULE)
    return "\n\n".join(parts)


def _declared(grounded: Grounded) -> set[str]:
    params = {p.name for p in grounded.params if p.annotation and parse_type(p.annotation)}
    return params | {f"self.{a}" for a, text in grounded.attr_annotations.items() if parse_type(text)}


def usage_problems(spec: InputSpec, grounded: Grounded, facts: CallerFacts) -> list[str]:
    """Spec types the function's own use of the input contradicts. Declared annotations, inputs the
    function rebinds or type-tests, and inputs typed object are never questioned."""
    typed = {**input_types(spec, grounded), **member_types(spec, grounded)}
    skip = facts.unchecked | _declared(grounded)
    problems = []
    for key in sorted(set(grounded.object_members) | set(facts.usage)):
        text = typed.get(key, "")
        shape = parse_type(text) if text else None
        if key in skip or shape is None or shape.kind == OBJECT:
            continue
        members = grounded.object_members.get(key, {})
        missing = sorted(m for m in members if m not in _MEMBERS[shape.kind])
        if missing:
            used = ", ".join(f".{m}()" if members[m] is not None else f".{m}" for m in missing)
            problems.append(f"input {key!r}: typed {text!r}, but the code uses {used} on it, which "
                            f"{shape.kind} does not have; type it object and give each member under stubs")
        use = facts.usage.get(key, Usage())
        if use.subscripted and shape.kind in _NOT_SUBSCRIPTABLE:
            problems.append(f"input {key!r}: typed {text!r}, but the code subscripts it ({key}[...])")
        if (use.iterated or use.sized) and shape.kind in _NOT_ITERABLE:
            problems.append(f"input {key!r}: typed {text!r}, but the code iterates it or passes it to len()")
    return problems
