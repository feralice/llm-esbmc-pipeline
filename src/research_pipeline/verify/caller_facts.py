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
    # (param, form) of each caller guard on an argument that holds at every call site (caller_guards).
    guards: tuple[tuple[str, str], ...] = ()


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


def _site_calls(graph: CallGraph, sites: list[CallSite]) -> list[tuple[ast.Module, ast.Call | None]]:
    trees: dict[str, ast.Module] = {}
    found = []
    for site in sites:
        if site.file not in trees:
            try:
                trees[site.file] = ast.parse("\n".join(graph.sources.get(site.file, [])))
            except (SyntaxError, ValueError, RecursionError):
                trees[site.file] = ast.Module(body=[], type_ignores=[])
        found.append((trees[site.file], _call_at(trees[site.file], site)))
    return found


def _bindings(call: ast.Call, grounded: Grounded) -> list[tuple[str, ast.expr]]:
    """(parameter, argument) for every argument the call passes by position or keyword."""
    positional = [p.name for p in grounded.params if not p.keyword]
    names = {p.name for p in grounded.params}
    # ``Class.method(obj, x)`` passes the receiver first: positions do not line up with the parameters.
    unbound = (isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name)
               and call.func.value.id == grounded.class_name and grounded.entry == "method")
    bound: list[tuple[str, ast.expr]] = []
    if not unbound:
        for name, arg in zip(positional, call.args):
            if isinstance(arg, ast.Starred):
                break
            bound.append((name, arg))
    return bound + [(k.arg, k.value) for k in call.keywords if k.arg in names]


def _passed(calls: list[tuple[ast.Module, ast.Call | None]], grounded: Grounded) -> dict[str, dict[str, int]]:
    passed: dict[str, dict[str, int]] = {}
    for _, call in calls:
        if call is None:
            continue
        for name, value in _bindings(call, grounded):
            kind = literal_type(value)
            if kind:
                counts = passed.setdefault(name, {})
                counts[kind] = counts.get(kind, 0) + 1
    return passed


_INVERSE = {ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.GtE: ast.Lt, ast.Gt: ast.LtE,
            ast.LtE: ast.Gt, ast.Is: ast.IsNot, ast.IsNot: ast.Is}
_FLIPPED = {ast.Eq: ast.Eq, ast.NotEq: ast.NotEq, ast.Lt: ast.Gt, ast.Gt: ast.Lt, ast.LtE: ast.GtE,
            ast.GtE: ast.LtE, ast.Is: ast.Is, ast.IsNot: ast.IsNot}
_SYMBOLS = {ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">="}
_GUARD_TYPES = frozenset({"int", "float", "bool", "str", "bytes", "list", "dict", "tuple", "set", "frozenset"})
_SIZED = frozenset({"str", "bytes", "list", "dict", "tuple", "set", "frozenset"})
TRUTHY = "truthy"  # the form of ``if x:``; every other form is a template with {} for the parameter
IS_NONE, NOT_NONE = "{} is None", "{} is not None"


def _atom(node: ast.expr, positive: bool) -> list[tuple[str, str]]:
    """(name, form) for one condition on a plain name, when ``node`` is true (``positive``) or false."""
    if isinstance(node, ast.Name):
        return [(node.id, TRUTHY)] if positive else []
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "isinstance"
            and len(node.args) == 2 and isinstance(node.args[0], ast.Name) and isinstance(node.args[1], ast.Name)
            and node.args[1].id in _GUARD_TYPES):
        return [(node.args[0].id, f"isinstance({{}}, {node.args[1].id})")] if positive else []
    if not (isinstance(node, ast.Compare) and len(node.ops) == 1 and type(node.ops[0]) in _INVERSE):
        return []
    subject, op, other = node.left, type(node.ops[0]), node.comparators[0]
    if isinstance(subject, ast.Constant):
        subject, op, other = other, _FLIPPED[op], subject
    op = op if positive else _INVERSE[op]
    sized = (isinstance(subject, ast.Call) and isinstance(subject.func, ast.Name) and subject.func.id == "len"
             and len(subject.args) == 1 and isinstance(subject.args[0], ast.Name))
    name = subject.args[0].id if sized else subject.id if isinstance(subject, ast.Name) else None
    if name is None or not isinstance(other, ast.Constant):
        return []
    if other.value is None and not sized and op in (ast.Is, ast.IsNot, ast.Eq, ast.NotEq):
        return [(name, IS_NONE if op in (ast.Is, ast.Eq) else NOT_NONE)]
    if type(other.value) in (int, float) and op in _SYMBOLS:
        return [(name, f"{'len({})' if sized else '{}'} {_SYMBOLS[op]} {other.value!r}")]
    return []


def _conditions(node: ast.expr, positive: bool) -> list[tuple[str, str]]:
    """What ``node`` being true (or false) says about plain names: ``a and b`` true gives both, ``a or b``
    false gives both negations, anything else nothing."""
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _conditions(node.operand, not positive)
    if isinstance(node, ast.BoolOp) and isinstance(node.op, ast.And if positive else ast.Or):
        return [c for value in node.values for c in _conditions(value, positive)]
    return _atom(node, positive)


_EXITS = (ast.Return, ast.Raise, ast.Continue, ast.Break)
_SCOPES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def _dominating(tree: ast.Module, call: ast.Call) -> list[tuple[str, str]]:
    """(name, form) for each condition that holds whenever ``call`` runs, up to the enclosing function:
    an enclosing ``if``, conditional expression or ``and``/``or``, and an earlier ``if ...: return`` in an
    enclosing block. A name assigned at or after the test (a loop may come back) is left out."""
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    found: list[tuple[str, str, ast.expr]] = []

    def add(test: ast.expr, positive: bool) -> None:
        found.extend((name, form, test) for name, form in _conditions(test, positive))

    node: ast.AST = call
    while id(node) in parents and not isinstance(node, _SCOPES):
        parent = parents[id(node)]
        if isinstance(parent, ast.If) and node is not parent.test:
            add(parent.test, node in parent.body)
        elif isinstance(parent, ast.IfExp) and node is not parent.test:
            add(parent.test, node is parent.body)
        elif isinstance(parent, ast.BoolOp):
            for value in parent.values[:parent.values.index(node)]:
                add(value, isinstance(parent.op, ast.And))
        for block in ("body", "orelse", "finalbody"):
            statements = getattr(parent, block, None)
            if isinstance(statements, list) and node in statements:
                for earlier in statements[:statements.index(node)]:
                    if isinstance(earlier, ast.If) and not earlier.orelse and isinstance(earlier.body[-1], _EXITS):
                        add(earlier.test, False)
        node = parent
    scope = node if isinstance(node, _SCOPES) else tree
    stores = [n for n in ast.walk(scope) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)]
    return [(name, form) for name, form, test in found
            if not any(n.id == name and n.lineno >= test.lineno and not any(n is t for t in ast.walk(test))
                       for n in stores)]


def caller_guards(calls: list[tuple[ast.Module, ast.Call | None]], grounded: Grounded,
                  used_as_value: bool) -> tuple[tuple[str, str], ...]:
    """The guards on an argument that every call site sits under, in the parameter's terms. A call site
    that cannot be read, or the function used as a value (calls out of sight), leaves none."""
    if not calls or used_as_value or any(call is None for _, call in calls):
        return ()
    common: set[tuple[str, str]] | None = None
    for tree, call in calls:
        params: dict[str, set[str]] = {}
        for param, arg in _bindings(call, grounded):
            if isinstance(arg, ast.Name):
                params.setdefault(arg.id, set()).add(param)
        here = {(param, form) for name, form in _dominating(tree, call) for param in params.get(name, ())}
        common = here if common is None else common & here
    return tuple(sorted(common or ()))


def _guard_assumptions(param: str, form: str, kind: str, optional: bool) -> list[str] | None:
    """The assumptions a guard adds for an input of this type; None when no value of the type satisfies it.
    A guard every value of the type satisfies adds nothing."""
    present = [f"{param} is not None"] if optional else []
    if form == IS_NONE:
        return [form.format(param)] if optional else [] if kind == "none" else None
    if kind == "none":
        return None
    if form == NOT_NONE:
        return present
    if form.startswith("isinstance("):
        expected = form.removeprefix("isinstance({}, ").removesuffix(")")
        return present if kind in (expected, OBJECT) or (expected == "int" and kind == "bool") else None
    if form == TRUTHY:
        nonzero = {**dict.fromkeys(_SIZED, f"len({param}) > 0"), "int": f"{param} != 0", "float": f"{param} != 0",
                   "bool": param}
        return present + ([nonzero[kind]] if kind in nonzero else [])
    if form.startswith("len("):
        return present + [form.format(param)] if kind in _SIZED else [] if kind == OBJECT else None
    return present + [form.format(param)] if kind in ("int", "float", "bool") else []


def guard_assumptions(facts: CallerFacts, spec: InputSpec, grounded: Grounded) -> tuple[tuple[str, ...], list[str]]:
    """The caller guards as harness assumptions for the spec's types, and the spec types a guard contradicts
    (an assumption no input satisfies would make every check vacuous)."""
    types = input_types(spec, grounded)
    assumed: list[str] = []
    problems = []
    for param, form in facts.guards:
        shape = parse_type(types[param]) if types.get(param) else None
        if shape is None:
            continue
        wanted = _guard_assumptions(param, form, shape.kind, shape.optional)
        if wanted is None:
            condition = param if form == TRUTHY else form.format(param)
            problems.append(f"input {param!r}: every caller calls it only when {condition}, "
                            f"which no {types[param]!r} value satisfies")
            continue
        assumed += [a for a in wanted if a not in assumed and a not in spec.assumptions]
    return tuple(assumed), problems


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
    calls = _site_calls(graph, sites)
    references = _references(tree, source.splitlines(), grounded, h.function.split(".")[-1])
    return CallerFacts(
        sites="" if text == NO_CALLERS else text,
        site_count=len(sites),
        references=references,
        defaults=_defaults(function, params) if function is not None else {},
        passed=_passed(calls, grounded),
        usage=usage,
        unchecked=unchecked,
        guards=caller_guards(calls, grounded, bool(references)),
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
