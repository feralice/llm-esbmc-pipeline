"""What the call graph says beyond who calls whom: centrality, caller slices, architecture smells and
Feature Envy metrics. Each one feeds a flag or prompt variant; none changes the default pipeline."""

from __future__ import annotations

import ast
import re
import statistics
from collections import Counter

import networkx as nx

from .callgraph import CallGraph


def _function_graph(graph: CallGraph) -> nx.DiGraph:
    digraph = nx.DiGraph()
    digraph.add_nodes_from(graph.functions)
    digraph.add_edges_from((site.caller, site.callee) for site in graph.calls
                           if site.callee in graph.functions and site.caller in graph.functions)
    return digraph


def pagerank(graph: CallGraph) -> dict[str, float]:
    """Centrality of each function on the caller-to-callee graph (Zimmermann and Nagappan, ICSE 2008):
    a helper many functions reach ranks high."""
    digraph = _function_graph(graph)
    nodes = list(digraph)
    if not nodes:
        return {}
    # Power iteration, as nx.pagerank computes it without SciPy: dangling nodes spread their score evenly.
    n, damping = len(nodes), 0.85
    scores = dict.fromkeys(nodes, 1 / n)
    for _ in range(100):
        dangling = sum(scores[v] for v in nodes if digraph.out_degree(v) == 0)
        new = {v: (1 - damping) / n + damping * dangling / n
                  + damping * sum(scores[u] / digraph.out_degree(u) for u in digraph.predecessors(v)) for v in nodes}
        converged = sum(abs(new[v] - scores[v]) for v in nodes) < 1e-10
        scores = new
        if converged:
            break
    return scores


def _names(node: ast.AST | None) -> set[str]:
    return {n.id for n in ast.walk(node) if isinstance(n, ast.Name)} if node is not None else set()


def _definitions(function: ast.AST) -> list[tuple[ast.stmt, set[str], set[str]]]:
    """(statement, names it binds, names it reads) for every binding statement inside ``function``."""
    out = []
    for node in ast.walk(function):
        if isinstance(node, ast.Assign):
            out.append((node, set().union(*(_names(t) for t in node.targets)), _names(node.value)))
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign)):
            reads = _names(node.value) | (_names(node.target) if isinstance(node, ast.AugAssign) else set())
            out.append((node, _names(node.target), reads))
        elif isinstance(node, (ast.For, ast.AsyncFor)):
            out.append((node, _names(node.target), _names(node.iter)))
    return out


def _slice_lines(caller: ast.FunctionDef | ast.AsyncFunctionDef, call: ast.Call) -> tuple[set[int], set[str]]:
    """Lines of ``caller`` (relative to it) the call's arguments depend on, and the parameters reached."""
    params = {a.arg for a in [*caller.args.posonlyargs, *caller.args.args, *caller.args.kwonlyargs]}
    params |= {a.arg for a in (caller.args.vararg, caller.args.kwarg) if a}
    needed = set().union(*(_names(a) for a in [*call.args, *(k.value for k in call.keywords)]))
    definitions = [d for d in _definitions(caller) if d[0].lineno < call.lineno]
    lines: set[int] = set()
    changed = True
    while changed:  # the fixed point ends: each pass only adds names and lines from a finite set
        changed = False
        for statement, binds, reads in definitions:
            if binds & needed and statement.lineno not in lines:
                header = statement.lineno if isinstance(statement, (ast.For, ast.AsyncFor)) else statement.end_lineno
                lines.update(range(statement.lineno, (header or statement.lineno) + 1))
                needed |= reads
                changed = True
    return lines, needed & params


_GUARDS = (ast.If, ast.While, ast.For, ast.AsyncFor, ast.Try, ast.With, ast.AsyncWith)


def _guard_headers(function: ast.AST, lines: set[int]) -> set[int]:
    """Header lines of the if/while/for/try/with blocks enclosing ``lines``: the caller's filters."""
    headers = set()
    for node in ast.walk(function):
        if isinstance(node, _GUARDS) and node.body and any(
                node.body[0].lineno <= line <= (node.end_lineno or node.lineno) for line in lines):
            headers.update(range(node.lineno, node.body[0].lineno))
            for branch in getattr(node, "orelse", []):  # an elif is an If in orelse: keep its test line too
                if isinstance(branch, ast.If) and any(branch.lineno <= line <= (branch.end_lineno or 0)
                                                      for line in lines):
                    headers.add(branch.lineno)
    return headers


def _definition_at(tree: ast.Module, line: int) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    return next((n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.lineno == line), None)


def _parsed(graph: CallGraph, file: str, cache: dict[str, ast.Module | None]) -> ast.Module | None:
    """The whole file parsed once: a method sliced out of it may not parse alone (a column-0 docstring)."""
    if file not in cache:
        try:
            cache[file] = ast.parse("\n".join(graph.sources.get(file, [])))
        except (SyntaxError, ValueError):
            cache[file] = None
    return cache[file]


def _calls_to(caller: ast.AST, name: str, line: int) -> list[ast.Call]:
    def target(call: ast.Call) -> str:
        func = call.func
        return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else ""
    return [n for n in ast.walk(caller) if isinstance(n, ast.Call) and n.lineno == line and target(n) == name]


def caller_slices(graph: CallGraph, key: str, *, max_chars: int = 3_000, rename: bool = True) -> str:
    """For each call to ``key``, only the caller's lines its arguments depend on (a backward slice inside
    the caller, as LLMxCPG slices a code property graph for the LLM), the if/while/for/try headers around
    them, and the call itself."""
    function = graph.functions[key]
    cache: dict[str, ast.Module | None] = {}
    blocks, seen = [], set()
    for site in graph.callers(key):
        caller = graph.functions.get(site.caller)
        tree = _parsed(graph, site.file, cache)
        if caller is None or tree is None or (site.file, site.line) in seen:
            continue
        seen.add((site.file, site.line))
        node = _definition_at(tree, caller.start_line)
        calls = _calls_to(node, function.name, site.line) if node is not None else []
        if not calls:
            continue
        kept: set[int] = set(range(site.line, site.end_line + 1))
        reached: set[str] = set()
        for call in calls:
            lines, params = _slice_lines(node, call)
            kept |= lines
            reached |= params
        kept |= _guard_headers(node, kept)
        source = graph.sources[site.file]
        blocks.append("\n".join([f"# call in {caller.qualname}, {site.file}, line {site.line}:",
                                 *(f"# parameter: {name}" for name in sorted(reached)),
                                 *(f"{n:>5} | {source[n - 1].rstrip()}" for n in sorted(kept))]))
    text = ""
    for block in blocks:  # whole blocks only, as caller_context does, so the rename never sees a cut name
        if text and len(text) + len(block) + 1 > max_chars:
            break
        text = f"{text}\n{block}" if text else block[:max_chars]
    return re.sub(rf"\b{re.escape(function.name)}\b", "target_function", text) if rename else text


def _module_graph(graph: CallGraph) -> nx.DiGraph:
    digraph = nx.DiGraph()
    digraph.add_nodes_from(graph.modules)
    for site in graph.calls:
        caller = site.caller.split(":", 1)[0]
        callee = graph.functions[site.callee].module if site.callee in graph.functions else None
        if callee and caller != callee:
            digraph.add_edge(caller, callee)
    return digraph


def architecture_smells(graph: CallGraph) -> list[dict]:
    """Cyclic and hub-like dependencies between modules, as Arcan finds them on the dependency graph
    (Arcelli Fontana et al., ICSA Workshops 2017). Deterministic: no LLM."""
    digraph = _module_graph(graph)
    smells = [{"smell": "cyclic_dependency", "modules": sorted(component),
               "evidence": " -> ".join(sorted(component)) + " call each other"}
              for component in nx.strongly_connected_components(digraph) if len(component) > 1]
    if digraph.number_of_nodes():
        fan_in, fan_out = dict(digraph.in_degree()), dict(digraph.out_degree())
        median_in, median_out = statistics.median(fan_in.values()), statistics.median(fan_out.values())
        for module in sorted(digraph):
            if fan_in[module] > median_in and fan_out[module] > median_out:
                smells.append({"smell": "hub_like_dependency", "modules": [module],
                               "evidence": f"fan-in {fan_in[module]}, fan-out {fan_out[module]} "
                                           f"(medians {median_in}, {median_out})"})
    return smells



def _method_ast(graph: CallGraph, key: str) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    function = graph.functions[key]
    tree = _parsed(graph, function.file, {})
    return _definition_at(tree, function.start_line) if tree is not None else None


def feature_envy_metrics(graph: CallGraph, key: str) -> dict:
    """How much a method uses its own object against each object passed to it: the tool output iSMELL
    (ASE 2024) puts in the prompt. Only parameters count as other objects (a module or a local list is not
    a class the method could move to); ``foreign_calls`` counts calls into other modules of the graph."""
    node = _method_ast(graph, key)
    own, foreign = 0, Counter()
    if node is not None:
        params = [a.arg for a in [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]]
        static = any(isinstance(d, ast.Name) and d.id == "staticmethod" for d in node.decorator_list)
        receiver = None if static or not params else params[0]
        others = set(params) - {receiver}
        for attribute in ast.walk(node):
            if isinstance(attribute, ast.Attribute) and isinstance(attribute.value, ast.Name):
                if attribute.value.id == receiver:
                    own += 1
                elif attribute.value.id in others:
                    foreign[attribute.value.id] += 1
    module = graph.functions[key].module
    calls = Counter(graph.functions[s.callee].module for s in graph.callees(key)
                    if graph.functions[s.callee].module != module)
    return {"own_accesses": own, "foreign_accesses": dict(foreign), "foreign_calls": dict(calls)}


def envy_candidates(graph: CallGraph) -> list[str]:
    """Methods that touch some other object more than their own."""
    out = []
    for key, function in graph.functions.items():
        if not function.class_qualname:
            continue
        metrics = feature_envy_metrics(graph, key)
        if max(metrics["foreign_accesses"].values(), default=0) > metrics["own_accesses"]:
            out.append(key)
    return out
