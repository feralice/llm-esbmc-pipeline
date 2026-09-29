"""Static provenance and bug-grounding gates for LLM compatibility rewrites."""

from __future__ import annotations

import ast
import builtins
import copy
import symtable
import textwrap
from dataclasses import dataclass

from .rewrite import RewriteProposal

_INTRINSICS = {
    "nondet_int", "nondet_float", "nondet_bool", "nondet_str",
    "nondet_list", "nondet_dict", "__ESBMC_assume",
}


@dataclass(frozen=True)
class GuardReport:
    ok: bool
    reasons: tuple[str, ...] = ()
    suspect_rewrite_line: int | None = None
    risk: str = "semantic"
    manifest_matches: bool = True
    suspect_rewrite_end_line: int | None = None
    stubs: tuple[str, ...] = ()


def _find_function(tree: ast.Module, qualified_name: str) -> ast.FunctionDef | None:
    parts = qualified_name.split(".")
    if len(parts) == 1:
        matches = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and node.name == parts[0]]
    elif len(parts) == 2:
        classes = [node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == parts[0]]
        matches = [method for cls in classes for method in cls.body
                   if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                   and method.name == parts[1]]
    else:
        return None
    return matches[0] if len(matches) == 1 and isinstance(matches[0], ast.FunctionDef) else None


def _expression_nodes(function: ast.FunctionDef, expression: str) -> list[ast.AST]:
    """Nodes equal to the suspect; datasets give either an expression or one statement."""
    try:
        suspect: ast.AST = ast.parse(expression, mode="eval").body
        kind: type = ast.expr
    except SyntaxError:
        try:
            body = ast.parse(textwrap.dedent(expression).strip()).body
        except SyntaxError:
            return []
        if len(body) != 1:
            return []
        suspect, kind = body[0], ast.stmt
    wanted = ast.dump(suspect, include_attributes=False)
    return [node for node in ast.walk(function)
            if isinstance(node, kind) and ast.dump(node, include_attributes=False) == wanted]


def _step(node: ast.AST, field: str, index: int) -> str | None:
    """Label for descending from ``node`` into ``field`` when that choice guards evaluation."""
    if isinstance(node, (ast.If, ast.While, ast.IfExp)) and field in {"body", "orelse"}:
        return f"{type(node).__name__}.{field}:{ast.dump(node.test, include_attributes=False)}"
    if isinstance(node, ast.BoolOp) and field == "values":
        return f"BoolOp.{type(node.op).__name__}.{index}"
    if isinstance(node, ast.stmt) and not isinstance(node, ast.FunctionDef) and field in {
        "body", "orelse", "finalbody", "handlers",
    }:
        return f"{type(node).__name__}.{field}"
    if isinstance(node, ast.comprehension) and field == "ifs":
        return "comprehension.ifs"
    return None


def _control_path(function: ast.FunctionDef, target: ast.AST) -> tuple[str, ...] | None:
    """Enclosing guards from the function down to ``target``, with the branch taken."""
    def walk(node: ast.AST, path: tuple[str, ...]) -> tuple[str, ...] | None:
        if node is target:
            return path
        for name, value in ast.iter_fields(node):
            children = value if isinstance(value, list) else [value]
            for index, child in enumerate(children):
                if not isinstance(child, ast.AST):
                    continue
                label = _step(node, name, index)
                found = walk(child, (*path, label) if label else path)
                if found is not None:
                    return found
        return None
    return walk(function, ())


def _control_signature(function: ast.FunctionDef) -> tuple[str, ...]:
    signature: list[str] = []
    for node in ast.walk(function):
        if isinstance(node, (ast.If, ast.While, ast.Assert)):
            value = node.test
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            value = node.iter
        elif isinstance(node, ast.Raise):
            value = node.exc
        elif isinstance(node, ast.Match):
            value = node.subject
        else:
            continue
        signature.append(ast.dump(value, include_attributes=False) if value else type(node).__name__)
    return tuple(signature)


def _defined_global_names(table: symtable.SymbolTable) -> set[str]:
    return {
        symbol.get_name() for symbol in table.get_symbols()
        if symbol.is_assigned() or symbol.is_imported() or symbol.is_namespace()
    }


def _undefined_globals(source: str, filename: str) -> set[str]:
    table = symtable.symtable(source, filename, "exec")
    module_names = _defined_global_names(table)
    undefined: set[str] = set()
    pending = [table]
    while pending:
        current = pending.pop()
        pending.extend(current.get_children())
        if current is table:
            continue
        for symbol in current.get_symbols():
            name = symbol.get_name()
            if (symbol.is_global() and name not in module_names
                    and not hasattr(builtins, name) and name not in _INTRINSICS):
                undefined.add(name)
    return undefined


def _instances_of(driver: ast.Module, class_name: str) -> set[str]:
    return {
        target.id
        for node in ast.walk(driver) if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name)
        and node.value.func.id == class_name
        for target in node.targets if isinstance(target, ast.Name)
    }


def _target_calls(driver: ast.Module, qualified_name: str) -> list[ast.Call]:
    """Calls of a free function by name, or of a method on an instance of its class."""
    parts = qualified_name.split(".")
    calls = [node for node in ast.walk(driver) if isinstance(node, ast.Call)]
    if len(parts) == 1:
        return [node for node in calls if isinstance(node.func, ast.Name) and node.func.id == parts[0]]
    if len(parts) != 2:
        return []
    class_name, method = parts
    instances = _instances_of(driver, class_name)

    def on_instance(receiver: ast.expr) -> bool:
        if isinstance(receiver, ast.Name):
            return receiver.id in instances
        return (isinstance(receiver, ast.Call) and isinstance(receiver.func, ast.Name)
                and receiver.func.id == class_name)

    return [node for node in calls
            if isinstance(node.func, ast.Attribute) and node.func.attr == method
            and on_instance(node.func.value)]


def _is_nondet(node: ast.AST | None) -> bool:
    return (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id.startswith("nondet_"))


def _nondet_flows_into(driver: ast.Module, call: ast.Call) -> bool:
    """Every nondet value is an argument of ``call``, inline or via a local assigned once."""
    direct = [arg for arg in [*call.args, *(kw.value for kw in call.keywords)] if isinstance(arg, ast.Name)]
    assigned: dict[str, int] = {}
    for node in ast.walk(driver):
        targets = node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(
            node, (ast.AnnAssign, ast.AugAssign)) else []
        for target in targets:
            if isinstance(target, ast.Name):
                assigned[target.id] = assigned.get(target.id, 0) + 1
    bound = {arg.id for arg in direct if assigned.get(arg.id) == 1}
    inline = {id(node) for node in ast.walk(call) if _is_nondet(node)}
    for node in ast.walk(driver):
        if not _is_nondet(node) or id(node) in inline:
            continue
        owner = next((stmt for stmt in ast.walk(driver)
                      if isinstance(stmt, (ast.Assign, ast.AnnAssign)) and stmt.value is not None
                      and any(child is node for child in ast.walk(stmt.value))), None)
        targets = [] if owner is None else owner.targets if isinstance(owner, ast.Assign) else [owner.target]
        if not (len(targets) == 1 and isinstance(targets[0], ast.Name) and targets[0].id in bound):
            return False
    return True


def _driver_shape_problem(driver: ast.Module, module: ast.Module) -> str:
    """The driver may only define ``main`` and call it; it must not rebind module names."""
    body = driver.body
    if not (len(body) == 2 and isinstance(body[0], ast.FunctionDef) and body[0].name == "main"
            and isinstance(body[1], ast.Expr)):
        return "driver must contain only def main() and a module-level main() call"
    module_names = {name for node in module.body if isinstance(node, _TOP_LEVEL_BINDINGS)
                    for name in _bound_names(node)}
    for node in (child for stmt in body[0].body for child in ast.walk(stmt)):
        if isinstance(node, (ast.Global, ast.Nonlocal, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef, ast.Import, ast.ImportFrom, ast.Lambda)):
            return f"driver must not use {type(node).__name__} inside main()"
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id in module_names:
            return f"driver rebinds module name {node.id!r}"
    return ""


_TOP_LEVEL_BINDINGS = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import, ast.ImportFrom, ast.Assign, ast.AnnAssign,
)


def _bound_names(node: ast.stmt) -> set[str]:
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return {(alias.asname or alias.name).split(".")[0] for alias in node.names}
    return {child.id for child in ast.walk(node) if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Store)}


# Modules ESBMC-Python models (src/python-frontend/models); their imports must stay.
_MODELED_MODULES = frozenset({
    "builtins", "cmath", "collections", "dataclasses", "datetime", "decimal", "enum", "heapq",
    "math", "numpy", "os", "queue", "random", "re", "string", "sys", "threading", "time", "typing",
})


def _import_bindings(tree: ast.Module) -> dict[str, str]:
    """Top-level imported name -> root module."""
    bound = {}
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                bound[(alias.asname or alias.name).split(".")[0]] = alias.name.split(".")[0]
        elif isinstance(node, ast.ImportFrom):
            root = "." if node.level else (node.module or "").split(".")[0]
            for alias in node.names:
                bound[alias.asname or alias.name] = root
    return bound


def _is_havoc_value(node: ast.AST | None) -> bool:
    """None, a constant, a nondet call, or a container of those: no computation."""
    if node is None or isinstance(node, ast.Constant) or _is_nondet(node):
        return True
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return all(_is_havoc_value(element) for element in node.elts)
    if isinstance(node, ast.Dict):
        return all(_is_havoc_value(part) for part in [*node.keys, *node.values])
    return False


def _is_stub_function(node: ast.FunctionDef) -> bool:
    body = node.body
    if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    return len(body) == 1 and (
        isinstance(body[0], ast.Pass)
        or (isinstance(body[0], ast.Return) and _is_havoc_value(body[0].value))
    )


def _top_level(tree: ast.Module) -> dict[str, ast.stmt]:
    named = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            named[node.name] = node
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    named[target.id] = node
    return named


def _stub_report(original: ast.Module, rewritten: ast.Module, function: str):
    """Validate havoc stubs for names the original cannot resolve.

    A stub may only stand for a name the original leaves undefined or imports
    from a module ESBMC does not model, and its body is a nondet/constant
    return. With stubs, every other original definition must stay unchanged
    apart from annotations, because the original can no longer be replayed.
    """
    original_imports = _import_bindings(original)
    rewritten_imports = _import_bindings(rewritten)
    problems: list[str] = []
    for name, module in original_imports.items():
        if name not in rewritten_imports and module in _MODELED_MODULES:
            problems.append(f"removed import of ESBMC-modeled module {module!r}")
    unmodeled = {name for name, module in original_imports.items() if module not in _MODELED_MODULES}
    try:
        undefined = _undefined_globals(ast.unparse(original), "<original>")
    except SyntaxError:
        undefined = set()
    stubbable = (unmodeled - set(rewritten_imports)) | undefined

    original_defs = _top_level(original)
    stubs: list[str] = []
    stub_nodes: list[ast.stmt] = []
    for name, node in _top_level(rewritten).items():
        if name in original_defs:
            continue
        if name not in stubbable:
            problems.append(f"new definition {name!r} is not a stub for an unresolved name")
            continue
        valid = (_is_stub_function(node) if isinstance(node, ast.FunctionDef)
                 else isinstance(node, (ast.Assign, ast.AnnAssign)) and _is_havoc_value(node.value))
        if not valid:
            problems.append(f"stub {name!r} must only return a nondet value, a constant or None")
            continue
        stubs.append(name)
        stub_nodes.append(node)
    if stubs:
        target = function.split(".")[0]
        rewritten_defs = _top_level(rewritten)
        for name, node in original_defs.items():
            if name == target or name not in rewritten_defs:
                continue
            before, after = copy.deepcopy(node), copy.deepcopy(rewritten_defs[name])
            _StripAnnotations().visit(before)
            _StripAnnotations().visit(after)
            if ast.dump(before, include_attributes=False) != ast.dump(after, include_attributes=False):
                problems.append(f"definition {name!r} changed beyond annotations in a stubbed rewrite")
    return tuple(sorted(stubs)), stub_nodes, problems


def _manifest_reconstructs(original_source: str, rewritten_source: str, proposal: RewriteProposal) -> bool:
    reconstructed = original_source
    for change in proposal.changes:
        if original_source.count(change.before) != 1 or rewritten_source.count(change.after) != 1:
            return False
        if reconstructed.count(change.before) != 1:
            return False
        reconstructed = reconstructed.replace(change.before, change.after, 1)
    try:
        return ast.dump(ast.parse(reconstructed), include_attributes=False) == ast.dump(
            ast.parse(rewritten_source), include_attributes=False
        )
    except SyntaxError:
        return False


def _assertions(tree: ast.Module) -> tuple[str, ...]:
    return tuple(sorted(ast.dump(node, include_attributes=False)
                         for node in ast.walk(tree) if isinstance(node, ast.Assert)))


def _nondet_calls(tree: ast.Module) -> tuple[str, ...]:
    return tuple(sorted(node.func.id for node in ast.walk(tree)
                         if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                         and node.func.id.startswith("nondet_")))


class _StripAnnotations(ast.NodeTransformer):
    def visit_arg(self, node: ast.arg):
        node.annotation = None
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        node.returns = None
        return self.generic_visit(node)


def validate_rewrite(
    original_source: str,
    proposal: RewriteProposal,
    *,
    function: str,
    expression: str,
    category: str,
    trusted_oracle: str | None = None,
) -> GuardReport:
    """Validate declared changes, the suspect operation, and driver provenance."""
    reasons: list[str] = []
    try:
        original_tree = ast.parse(original_source)
        rewritten_tree = ast.parse(proposal.rewritten_source)
        driver_tree = ast.parse(proposal.driver_source)
    except SyntaxError as exc:
        return GuardReport(False, (f"invalid Python syntax: {exc.msg}",))

    # The stage records the computed diff, so an inexact LLM manifest is noted, not fatal.
    manifest_matches = _manifest_reconstructs(original_source, proposal.rewritten_source, proposal)

    original_function = _find_function(original_tree, function)
    rewritten_function = _find_function(rewritten_tree, function)
    if original_function is None or rewritten_function is None:
        reasons.append("target function is missing or ambiguous")
        return GuardReport(False, tuple(reasons))

    original_suspects = _expression_nodes(original_function, expression)
    rewritten_suspects = _expression_nodes(rewritten_function, expression)
    if len(original_suspects) != 1 or len(rewritten_suspects) != 1:
        reasons.append("suspect expression is missing or ambiguous in original/rewritten function")
    elif _control_signature(original_function) != _control_signature(rewritten_function):
        reasons.append("control/precondition structure changed around the target function")
    elif (_control_path(original_function, original_suspects[0])
          != _control_path(rewritten_function, rewritten_suspects[0])):
        reasons.append("suspect expression moved to a different control-flow position")

    if proposal.oracle_ref is not None and proposal.oracle_ref != trusted_oracle:
        reasons.append("LLM oracle reference is not trusted configuration")

    driver_problem = _driver_shape_problem(driver_tree, rewritten_tree)
    if driver_problem:
        reasons.append(driver_problem)
    if any(isinstance(node, ast.Assert) for node in ast.walk(driver_tree)):
        reasons.append("driver must not introduce assert properties")
    if _assertions(original_tree) != _assertions(rewritten_tree):
        reasons.append("rewritten source added or removed assert properties")
    if not any(isinstance(node, ast.Expr) and isinstance(node.value, ast.Call)
               and isinstance(node.value.func, ast.Name) and node.value.func.id == "main"
               for node in driver_tree.body):
        reasons.append("driver has no module-level main() invocation")

    target_calls = _target_calls(driver_tree, function)
    if len(target_calls) != 1:
        reasons.append("driver must call the target exactly once")
    else:
        if not _nondet_flows_into(driver_tree, target_calls[0]):
            reasons.append("nondet value is disconnected from target call inputs")

    combined = proposal.rewritten_source + "\n" + proposal.driver_source
    try:
        undefined = _undefined_globals(combined, "<rewrite>")
    except SyntaxError as exc:
        undefined = {f"syntax:{exc.msg}"}
    if undefined:
        reasons.append("undefined name(s): " + ", ".join(sorted(undefined)))

    stubs, stub_nodes, stub_problems = _stub_report(original_tree, rewritten_tree, function)
    reasons.extend(stub_problems)
    stub_ids = {id(node) for stub in stub_nodes for node in ast.walk(stub)}
    added_nondet = {
        node.func.id for node in ast.walk(rewritten_tree)
        if _is_nondet(node) and id(node) not in stub_ids
    } - set(_nondet_calls(original_tree))
    if added_nondet:
        reasons.append("rewritten source introduced nondet call(s): " + ", ".join(sorted(added_nondet)))

    line = rewritten_suspects[0].lineno if len(rewritten_suspects) == 1 else None
    end_line = rewritten_suspects[0].end_lineno if len(rewritten_suspects) == 1 else None
    original_copy = copy.deepcopy(original_function)
    rewritten_copy = copy.deepcopy(rewritten_function)
    _StripAnnotations().visit(original_copy)
    _StripAnnotations().visit(rewritten_copy)
    risk = "structural" if ast.dump(original_copy, include_attributes=False) == ast.dump(
        rewritten_copy, include_attributes=False
    ) else "semantic"
    if stubs:
        risk = "stubbed"
    if category == "" or not expression.strip():
        reasons.append("candidate category/expression is missing")
    return GuardReport(not reasons, tuple(reasons), line, risk, manifest_matches, end_line, stubs)
