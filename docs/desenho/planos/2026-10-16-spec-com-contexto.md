# Spec com contexto dos chamadores: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** mostrar ao LLM do spec as chamadas reais da função alvo, as referências sem chamada e fatos estáticos de cada entrada, e rejeitar antes do ESBMC um tipo que o uso dentro da função contradiz, devolvendo o motivo pelo laço de reparo que já existe.

**Architecture:** módulo novo `src/research_pipeline/verify/caller_facts.py` (só AST) com `collect_facts`, `render_section` e `usage_problems`. Ele reaproveita o grafo do modo scan: `build_source_callgraph` (novo, em `scan/callgraph.py`) monta o grafo de um arquivo só, e `caller_context(..., rename=False)` formata as chamadas. `verify_hypothesis` ganha `spec_context` (`"none"` ou `"callers"`) e `graph`; a CLI ganha `--spec-context` (padrão `callers`), que entra no fingerprint. A checagem fica fora de `spec_problems`, porque `render_program` e o `precheck` usam `spec_problems` com um spec provisório todo `int`.

**Tech Stack:** Python 3 do `.venv`, `ast`, pytest, `research_pipeline.scan.callgraph`, `research_pipeline.scan.context`, `research_pipeline.verify.{grounding,spec,loop}`.

**Spec:** `docs/desenho/specs/2026-10-16-spec-com-contexto-design.md`

## Global Constraints

- Nenhuma chamada a LLM real e nenhum ESBMC real: testes com LLM falso (padrão de `tests/test_verify_llm_input.py` e `FakeLLM` de `tests/test_verify_loop.py`) e `run_esbmc_direct`/`concrete_replay` trocados por falsos.
- Nenhuma rodada, nenhuma medição: a comparação `--spec-context none` contra `callers` é do item 6.
- `verify_hypothesis(..., spec_context="none")` por padrão: `scripts/v2_replay_specs.py` e `scripts/v2_verify_smoke.py` não podem mudar de comportamento.
- `usage_problems` nunca entra em `spec_problems` (quebraria o `precheck`, que renderiza spec todo `int`).
- O item 2 está mexendo em `loop.py` em paralelo (parâmetro `rules`). Editar por trecho de texto, nunca por número de linha, e manter o que o item 2 já tiver colocado.
- Mudar `src/research_pipeline/prompts/input_spec_prompt.txt` muda o fingerprint V2: a rodada pausada em `artifacts/v2/final-2026-10-15-codex` deixa de ser retomável com este código. Não tentar contornar.
- Sem travessão em texto; sem commit sem a Fernanda pedir (cada tarefa termina em "ponto de parada").
- Teste de um arquivo: `.venv/bin/python -m pytest tests/<arquivo> -q`. Suíte: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`.

## Review Focus

1. **Spec provisório do `precheck` rejeitado pela checagem nova** (casos virariam `UNSUPPORTED` antes do LLM). A checagem roda só no laço: `test_without_context_the_prompt_is_unchanged` e `test_spec_contradicted_by_usage_is_sent_back_with_the_reason` (Tarefa 4), que passam pelo `precheck` com tudo `int`.
2. **Rejeitar tipo certo de entrada reatribuída ou testada** (`tz = groups[tz]` em `ip_real_32`; `isinstance`). Testes `test_rebound_shadowed_and_type_tested_inputs_are_unchecked` (Tarefa 2) e `test_rebound_or_type_tested_input_is_never_questioned` (Tarefa 3).
3. **Rejeitar anotação declarada**, que o LLM não pode mudar (daria `SPEC_FAILED` certo). Teste `test_declared_annotation_is_never_questioned` (Tarefa 3).
4. **Ligar argumento ao parâmetro errado** (`Classe.m(obj, 5)` desloca as posições; função definida duas vezes mostra chamadores da outra). Testes `test_method_called_unbound_through_the_class_binds_keywords_only` e `test_a_function_defined_twice_gets_no_callers` (Tarefa 2).
5. **Mudar o pedido de quem não pediu contexto** (reaplicação de specs, `--spec-context none`) ou deixar a escolha fora do fingerprint. Testes `test_without_context_the_prompt_is_unchanged` (Tarefa 4) e `test_spec_context_defaults_to_callers_and_enters_the_fingerprint` (Tarefa 5).

---

### Tarefa 1: grafo de um arquivo e contexto com o nome real

**Files:**
- Modify: `src/research_pipeline/scan/callgraph.py`
- Modify: `src/research_pipeline/scan/context.py`
- Test: `tests/test_scan_context.py`

**Interfaces:**
- Produces: `build_source_callgraph(source: str, filename: str) -> CallGraph` (levanta `SyntaxError`/`ValueError` se não fizer parse; módulo = `Path(filename).stem`, `file` = `Path(filename).name`).
- Produces: `caller_context(graph: CallGraph, key: str, *, before: int = 3, after: int = 1, max_sites: int = MAX_SITES, max_chars: int = MAX_CHARS, rename: bool = True) -> str`.

- [ ] **Passo 1: testes que falham.** Acrescentar ao fim de `tests/test_scan_context.py`:

```python


def test_single_source_graph_finds_in_file_callers_without_a_directory() -> None:
    from research_pipeline.scan.callgraph import build_source_callgraph

    graph = build_source_callgraph(SOURCE, "dataset/arquivo_com_bug/m.py")
    assert [site.line for site in graph.callers("m:ratio")] == [10, 11]
    assert graph.functions["m:ratio"].file == "m.py"


def test_single_source_graph_raises_on_a_file_that_does_not_parse() -> None:
    import pytest

    from research_pipeline.scan.callgraph import build_source_callgraph

    with pytest.raises(SyntaxError):
        build_source_callgraph("def broken(:\n", "m.py")


def test_context_can_keep_the_real_name_for_the_spec_prompt(tmp_path: Path) -> None:
    text = caller_context(_graph(tmp_path, SOURCE), "m:ratio", rename=False)
    assert "return ratio(1, n)" in text and "target_function" not in text
```

- [ ] **Passo 2: rodar e ver falhar.**

Run: `.venv/bin/python -m pytest tests/test_scan_context.py -q`
Expected: 3 falhas: duas com `ImportError: cannot import name 'build_source_callgraph'` e uma com `TypeError: caller_context() got an unexpected keyword argument 'rename'`.

- [ ] **Passo 3: implementar.** Em `src/research_pipeline/scan/callgraph.py`, logo depois de `build_callgraph` (antes de `class _Builder:`):

```python
def build_source_callgraph(source: str, filename: str) -> CallGraph:
    """The graph of one file on its own: the verification source, whose project is not on disk.
    Raises SyntaxError or ValueError when ``source`` does not parse."""
    path = Path(filename)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        tree = ast.parse(source, filename=path.name)
    module = _Module(path.stem, path.name, tree, False, source.splitlines())
    return _Builder(path.parent.resolve(), {module.name: module}, []).build()
```

Em `src/research_pipeline/scan/context.py`, trocar a assinatura e a docstring de `caller_context`:

```python
def caller_context(graph: CallGraph, key: str, *, before: int = 3, after: int = 1, max_sites: int = MAX_SITES,
                   max_chars: int = MAX_CHARS, rename: bool = True) -> str:
    """The detection prompt renames the function to ``target_function`` and the context follows suit
    (``rename``); the spec prompt names the function, so it keeps the real name."""
```

e a última linha da função:

```python
    return re.sub(rf"\b{re.escape(function.name)}\b", "target_function", text) if rename else text
```

- [ ] **Passo 4: rodar e ver passar.**

Run: `.venv/bin/python -m pytest tests/test_scan_context.py tests/test_scan_callgraph.py tests/test_scan_pipeline.py -q`
Expected: todos passam (9 em `test_scan_context.py`).

- [ ] **Passo 5: ponto de parada (sem commit).** Mostrar o diff à Fernanda se ela pedir; não commitar.

---

### Tarefa 2: fatos dos chamadores e bloco do pedido

**Files:**
- Create: `src/research_pipeline/verify/caller_facts.py`
- Test: `tests/test_verify_caller_facts.py`

**Interfaces:**
- Consumes: `build_source_callgraph`, `caller_context(..., rename=False)` (Tarefa 1); `Grounded`, `ground` (`verify/grounding.py`); `find_function` (`verify/astutil.py`); `_shorten`, `CallGraph`, `CallSite` (`scan/callgraph.py`).
- Produces:
  - `@dataclass(frozen=True) class Usage: subscripted: bool = False; iterated: bool = False; sized: bool = False`
  - `@dataclass(frozen=True) class CallerFacts: sites: str = ""; site_count: int = 0; references: tuple[str, ...] = (); defaults: dict[str, str]; passed: dict[str, dict[str, int]]; usage: dict[str, Usage]; unchecked: frozenset[str] = frozenset()`
  - `literal_type(node: ast.expr) -> str | None`
  - `function_key(graph: CallGraph, file: str, qualname: str) -> str | None`
  - `collect_facts(h: BugHypothesis, grounded: Grounded, source: str, *, graph: CallGraph | None = None) -> CallerFacts`
  - `render_section(facts: CallerFacts, grounded: Grounded) -> str`
  - constantes `MAX_SITES = 5`, `MAX_CALLER_CHARS = 2_000`, `MAX_REFERENCES = 3`, `MAX_LINE_CHARS = 160`, `MAX_FACT_CHARS = 1_200`.

- [ ] **Passo 1: testes que falham.** Criar `tests/test_verify_caller_facts.py`:

```python
import ast

from research_pipeline.scan.callgraph import build_callgraph
from research_pipeline.verify.caller_facts import (
    MAX_CALLER_CHARS,
    CallerFacts,
    collect_facts,
    function_key,
    literal_type,
    render_section,
)
from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis

SOURCE = (
    "import re\n"                                                   # 1
    "from functools import partial\n"                               # 2
    "\n"                                                            # 3
    "def convert(string, match, ymd=None, d_m_y=None):\n"           # 4
    "    groups = match.groups()\n"                                 # 5
    "    return groups[ymd] + string\n"                             # 6
    "\n"                                                            # 7
    "def register(n):\n"                                            # 8
    "    return partial(convert, ymd=n + 1)\n"                      # 9
    "\n"                                                            # 10
    "def use(s):\n"                                                 # 11
    "    m = re.match('x', s)\n"                                    # 12
    "    return convert(s, m, 2, d_m_y=(1, 2, 3))\n"                # 13
)


def _facts(source=SOURCE, function="convert", expression="groups[ymd] + string", file="pkg/x.py", graph=None):
    h = BugHypothesis(file, function, expression)
    return collect_facts(h, ground(h, source), source, graph=graph), ground(h, source)


def test_literal_types_cover_constants_negatives_and_containers():
    def kind(text):
        return literal_type(ast.parse(text, mode="eval").body)

    assert [kind(t) for t in ("None", "True", "3", "-2.5", "'a'", "f'{x}'", "[1]", "(1,)", "{}", "{1}")] == [
        "None", "bool", "int", "float", "str", "str", "list", "tuple", "dict", "set"]
    assert kind("x") is None and kind("-x") is None and kind("n + 1") is None


def test_facts_from_the_verification_file_alone():
    facts, _ = _facts()
    assert facts.site_count == 1
    assert "return convert(s, m, 2, d_m_y=(1, 2, 3))" in facts.sites
    assert facts.passed == {"ymd": {"int": 1}, "d_m_y": {"tuple": 1}}
    assert facts.defaults == {"ymd": "None", "d_m_y": "None"}
    assert facts.usage == {}
    assert any("partial(convert, ymd=n + 1)" in line for line in facts.references)


def test_usage_marks_subscript_iteration_and_len():
    source = "def f(a, b, c, d):\n    for x in b:\n        pass\n    return a[0] + len(c) + d\n"
    facts, _ = _facts(source, "f", "a[0] + len(c) + d")
    assert facts.usage["a"].subscripted and facts.usage["b"].iterated and facts.usage["c"].sized
    assert "d" not in facts.usage


def test_rebound_shadowed_and_type_tested_inputs_are_unchecked():
    source = ("def f(a, b, c, d):\n    a = str(a)\n    g = lambda b: b\n"
              "    if isinstance(c, int):\n        return 0\n    return a[0] + g(b)[0] + c[0] + d[0]\n")
    facts, _ = _facts(source, "f", "a[0] + g(b)[0] + c[0] + d[0]")
    assert facts.unchecked == frozenset({"a", "b", "c"})
    assert set(facts.usage) == {"d"}


def test_method_called_unbound_through_the_class_binds_keywords_only():
    source = ("class C:\n    def m(self, x, y=0):\n        return x // y\n\n"
              "    def run(self):\n        return self.m(7, y='s')\n\n"
              "def outside(c):\n    return C.m(c, 5, y=0)\n")
    facts, _ = _facts(source, "C.m", "x // y")
    assert facts.passed == {"x": {"int": 1}, "y": {"int": 1, "str": 1}}


def test_a_function_defined_twice_gets_no_callers():
    source = "def f(a):\n    return a[0]\n\ndef f(a):\n    return a[0]\n\nf(1)\n"
    h = BugHypothesis("x.py", "f", "a[0]")
    facts = collect_facts(h, ground(h, "def f(a):\n    return a[0]\n"), source)
    assert facts.sites == "" and facts.site_count == 0 and facts.passed == {}


def test_scan_graph_finds_callers_in_other_files(tmp_path):
    (tmp_path / "calc.py").write_text("def first(xs):\n    return xs[0]\n", encoding="utf-8")
    (tmp_path / "app.py").write_text("from calc import first\n\ndef head():\n    return first([1, 2])\n",
                                     encoding="utf-8")
    graph = build_callgraph(tmp_path)
    source = (tmp_path / "calc.py").read_text(encoding="utf-8")
    assert function_key(graph, str(tmp_path / "calc.py"), "first") == "calc:first"
    facts, _ = _facts(source, "first", "xs[0]", file=str(tmp_path / "calc.py"), graph=graph)
    assert facts.passed == {"xs": {"list": 1}} and "app.py" in facts.sites


def test_a_source_that_does_not_parse_gives_empty_facts():
    h = BugHypothesis("x.py", "f", "a[0]")
    grounded = ground(h, "def f(a):\n    return a[0]\n")
    assert collect_facts(h, grounded, "def f(:\n") == CallerFacts()


def test_section_is_bounded_and_says_when_there_are_no_callers():
    facts, grounded = _facts()
    text = render_section(facts, grounded)
    assert "Call sites" in text and "- ymd: default is None; callers pass int (1x)" in text
    assert "- d_m_y: default is None; callers pass tuple (1x)" in text
    many = "def f(a):\n    return a[0]\n" + "".join(
        f"\ndef c{i}():\n    return f([{'1, ' * 60}1])\n" for i in range(30))
    big, _ = _facts(many, "f", "a[0]")
    assert len(big.sites) <= MAX_CALLER_CHARS + 60 and "omitida" in big.sites
    lonely, grounded = _facts("def f(a):\n    return a[0]\n", "f", "a[0]")
    assert "# none found in the verification source" in render_section(lonely, grounded)
```

- [ ] **Passo 2: rodar e ver falhar.**

Run: `.venv/bin/python -m pytest tests/test_verify_caller_facts.py -q`
Expected: erro de coleta `ModuleNotFoundError: No module named 'research_pipeline.verify.caller_facts'`.

- [ ] **Passo 3: implementar.** Criar `src/research_pipeline/verify/caller_facts.py`:

```python
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

MAX_SITES = 5
MAX_CALLER_CHARS = 2_000
MAX_REFERENCES = 3
MAX_LINE_CHARS = 160
MAX_FACT_CHARS = 1_200
# An input handed to one of these may hold several types; the harness picks one, so usage proves nothing.
_TYPE_TESTS = frozenset({"isinstance", "hasattr", "getattr", "type", "callable"})
_LITERALS = {ast.JoinedStr: "str", ast.List: "list", ast.ListComp: "list", ast.Tuple: "tuple", ast.Dict: "dict",
             ast.DictComp: "dict", ast.Set: "set", ast.SetComp: "set", ast.Lambda: "function"}


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
    return "\n\n".join(parts)
```

- [ ] **Passo 4: rodar e ver passar.**

Run: `.venv/bin/python -m pytest tests/test_verify_caller_facts.py -q`
Expected: `9 passed`.

- [ ] **Passo 5: ponto de parada (sem commit).**

---

### Tarefa 3: checagem de consistência entre tipo e uso

**Files:**
- Modify: `src/research_pipeline/verify/caller_facts.py`
- Test: `tests/test_verify_usage_problems.py`

**Interfaces:**
- Consumes: `CallerFacts`, `Usage` (Tarefa 2); `OBJECT`, `InputSpec`, `input_types`, `member_types`, `parse_type` (`verify/spec.py`).
- Produces: `usage_problems(spec: InputSpec, grounded: Grounded, facts: CallerFacts) -> list[str]`, em ordem alfabética de entrada; mensagens `"input {key!r}: typed {text!r}, but the code uses {members} on it, which {kind} does not have; type it object and give each member under stubs"`, `"input {key!r}: typed {text!r}, but the code subscripts it ({key}[...])"` e `"input {key!r}: typed {text!r}, but the code iterates it or passes it to len()"`.

- [ ] **Passo 1: testes que falham.** Criar `tests/test_verify_usage_problems.py`:

```python
from research_pipeline.verify.caller_facts import collect_facts, usage_problems
from research_pipeline.verify.grounding import ground
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.spec import InputSpec

SOURCE = ("def convert(match, ymd, rows, names: list):\n"
          "    groups = match.groups()\n"
          "    for row in rows:\n"
          "        pass\n"
          "    return groups[ymd] + names[0]\n")
GROUPS = ("input 'match': typed 'int', but the code uses .groups() on it, which int does not "
          "have; type it object and give each member under stubs")


def _check(params, source=SOURCE, function="convert", expression="groups[ymd] + names[0]", stubs=None):
    h = BugHypothesis("x.py", function, expression)
    grounded = ground(h, source)
    return usage_problems(InputSpec(params, {}, (), stubs or {}), grounded, collect_facts(h, grounded, source))


def test_int_with_a_called_member_is_rejected_with_the_member_named():
    assert _check({"match": "int", "ymd": "int", "rows": "list[int]"}) == [GROUPS]


def test_object_and_types_that_have_the_member_pass():
    assert _check({"match": "object", "ymd": "int", "rows": "list[int]"}, stubs={"match.groups": "list[str]"}) == []
    source = "def f(s):\n    return s.strip()[0]\n"
    assert _check({"s": "Optional[str]"}, source, "f", "s.strip()[0]") == []


def test_scalar_subscripted_or_iterated_is_rejected():
    source = "def f(a, b):\n    for x in b:\n        pass\n    return a[0]\n"
    problems = _check({"a": "int", "b": "Optional[float]"}, source, "f", "a[0]")
    assert problems == ["input 'a': typed 'int', but the code subscripts it (a[...])",
                        "input 'b': typed 'Optional[float]', but the code iterates it or passes it to len()"]
    assert _check({"a": "set[int]", "b": "str"}, source, "f", "a[0]") == [
        "input 'a': typed 'set[int]', but the code subscripts it (a[...])"]


def test_declared_annotation_is_never_questioned():
    source = "def f(a: int):\n    return a[0]\n"
    assert _check({}, source, "f", "a[0]") == []


def test_rebound_or_type_tested_input_is_never_questioned():
    source = ("def f(a, b):\n    a = str(a)\n    if isinstance(b, int):\n        return 0\n"
              "    return a.strip()[0] + b[0]\n")
    assert _check({"a": "int", "b": "int"}, source, "f", "a.strip()[0] + b[0]") == []


def test_receiver_attribute_and_member_stub_are_checked():
    source = "class C:\n    def m(self):\n        return self.re.match('x').group(1) + self.cron.RANGES.index(1)\n"
    h = BugHypothesis("x.py", "C.m", "self.cron.RANGES.index(1)")
    grounded = ground(h, source)
    spec = InputSpec({}, {"re": "str", "cron": "object"}, (), {"self.cron.RANGES": "int"})
    problems = usage_problems(spec, grounded, collect_facts(h, grounded, source))
    assert problems == [
        ("input 'self.cron.RANGES': typed 'int', but the code uses .index() on it, which int does not have; "
         "type it object and give each member under stubs"),
        ("input 'self.re': typed 'str', but the code uses .match() on it, which str does not have; "
         "type it object and give each member under stubs"),
    ]
```

- [ ] **Passo 2: rodar e ver falhar.**

Run: `.venv/bin/python -m pytest tests/test_verify_usage_problems.py -q`
Expected: erro de coleta `ImportError: cannot import name 'usage_problems' from 'research_pipeline.verify.caller_facts'`.

- [ ] **Passo 3: implementar.** Em `src/research_pipeline/verify/caller_facts.py`, acrescentar o import depois de `from .hypothesis import BugHypothesis`:

```python
from .spec import OBJECT, InputSpec, input_types, member_types, parse_type
```

as tabelas depois de `_LITERALS`:

```python
_MEMBERS = {kind: frozenset(dir(value)) for kind, value in {
    "int": int, "float": float, "bool": bool, "str": str, "bytes": bytes, "list": list, "tuple": tuple,
    "dict": dict, "set": set, "frozenset": frozenset, "none": None}.items()}
_NOT_SUBSCRIPTABLE = frozenset({"int", "float", "bool", "none", "set", "frozenset"})
_NOT_ITERABLE = frozenset({"int", "float", "bool", "none"})
```

e, no fim do arquivo:

```python
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
```

- [ ] **Passo 4: rodar e ver passar.**

Run: `.venv/bin/python -m pytest tests/test_verify_usage_problems.py tests/test_verify_caller_facts.py -q`
Expected: `15 passed`.

- [ ] **Passo 5: ponto de parada (sem commit).**

---

### Tarefa 4: bloco e checagem no laço do spec

**Files:**
- Modify: `src/research_pipeline/verify/loop.py`
- Test: `tests/test_verify_loop.py`

**Interfaces:**
- Consumes: `collect_facts`, `render_section`, `usage_problems` (Tarefas 2 e 3); `CallGraph` (`scan/callgraph.py`).
- Produces:
  - `SPEC_CONTEXTS = ("none", "callers")`
  - `_user_prompt(grounded: Grounded, previous: str, feedback: str, context: str = "") -> str`
  - `verify_hypothesis(..., strategy: str = "repair", <rules do item 2, se já existir>, spec_context: str = "none", graph: CallGraph | None = None) -> VerifyResult`
  - `VerifyResult.spec_context: dict` (`{"call_sites": int, "references": int, "chars": int}`), que `to_dict()` só inclui quando não vazio.

- [ ] **Passo 1: testes que falham.** Acrescentar ao fim de `tests/test_verify_loop.py`:

```python


CALLED = SOURCE + "\n\ndef mean(xs):\n    return ratio(sum(xs), len(xs))\n"
FIRST = "def first(rows, k):\n    return rows[k] // 1\n\n\ndef top(rows):\n    return first(rows, 0)\n"
FIRST_GOOD = json.dumps({"params": {"rows": "list[int]", "k": "int"}, "attributes": {}, "assumptions": []})


def _run_context(tmp_path, monkeypatch, llm, source, function, expression, **kwargs):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc("violation_found"))
    monkeypatch.setattr(loop, "concrete_replay", lambda program, function, **_: REPRODUCED)
    hypothesis = BugHypothesis("r.py", function, expression)
    return loop.verify_hypothesis(hypothesis, llm=llm, source=source, esbmc_command=["esbmc"], bound=5,
                                  timeout_seconds=30, work_dir=tmp_path, **kwargs)


def test_callers_context_reaches_every_prompt_and_is_recorded(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"total": "dict"}}), GOOD])
    result = _run_context(tmp_path, monkeypatch, llm, CALLED, "ratio", "total // count", spec_context="callers")
    assert result.verdict == CONFIRMED
    assert all("return ratio(sum(xs), len(xs))" in prompt for prompt in llm.prompts)
    assert result.to_dict()["spec_context"]["call_sites"] == 1


def test_without_context_the_prompt_is_unchanged(tmp_path, monkeypatch):
    llm = FakeLLM([GOOD])
    result = _run_context(tmp_path, monkeypatch, llm, CALLED, "ratio", "total // count")
    grounded, _, _ = loop.precheck(result.hypothesis, CALLED)
    assert llm.prompts == [loop._user_prompt(grounded, "", "")]
    assert "Call sites" not in llm.prompts[0] and "spec_context" not in result.to_dict()


def test_spec_contradicted_by_usage_is_sent_back_with_the_reason(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"rows": "int", "k": "int"}}), FIRST_GOOD])
    result = _run_context(tmp_path, monkeypatch, llm, FIRST, "first", "rows[k] // 1", spec_context="callers")
    assert result.verdict == CONFIRMED and len(result.attempts) == 2
    assert result.attempts[0]["problems"] == ["input 'rows': typed 'int', but the code subscripts it (rows[...])"]
    assert "but the code subscripts it" in llm.prompts[1]


def test_usage_rejections_until_the_budget_ends_give_spec_failed(tmp_path, monkeypatch):
    bad = json.dumps({"params": {"rows": "int", "k": "int"}})
    result = _run_context(tmp_path, monkeypatch, FakeLLM([bad, bad, bad]), FIRST, "first", "rows[k] // 1",
                          spec_context="callers")
    assert result.verdict == SPEC_FAILED and len(result.attempts) == 3


def test_unknown_spec_context_is_refused(tmp_path, monkeypatch):
    import pytest

    with pytest.raises(ValueError, match="spec_context"):
        _run_context(tmp_path, monkeypatch, FakeLLM([GOOD]), SOURCE, "ratio", "total // count", spec_context="all")
```

- [ ] **Passo 2: rodar e ver falhar.**

Run: `.venv/bin/python -m pytest tests/test_verify_loop.py -q`
Expected: 4 falhas com `TypeError: verify_hypothesis() got an unexpected keyword argument 'spec_context'`; `test_without_context_the_prompt_is_unchanged` já passa (não usa o argumento novo) e protege o comportamento antigo.

- [ ] **Passo 3: implementar.** Em `src/research_pipeline/verify/loop.py`:

Imports (antes de `from .astutil import undefined_globals`, e o de `caller_facts` logo depois dele):

```python
from ..scan.callgraph import CallGraph
from .astutil import undefined_globals
from .caller_facts import collect_facts, render_section, usage_problems
```

Depois de `STRATEGIES = ("repair", "resample")`:

```python
SPEC_CONTEXTS = ("none", "callers")
```

No `VerifyResult`, depois de `pytest: dict = field(default_factory=dict)`:

```python
    spec_context: dict = field(default_factory=dict)
```

e em `to_dict`, depois da linha do `pytest`:

```python
            **({"spec_context": self.spec_context} if self.spec_context else {}),
```

`_user_prompt`: trocar a assinatura por

```python
def _user_prompt(grounded: Grounded, previous: str, feedback: str, context: str = "") -> str:
```

e, logo depois do fechamento da lista `parts = [...]` (a linha do `"Code (verbatim slice of the real module)..."` e o `]`), antes de `if previous:`:

```python
    if context:
        parts.append(context)
```

`verify_hypothesis`: acrescentar ao fim dos parâmetros nomeados (depois de `strategy` e, se o item 2 já tiver entrado, depois de `rules`):

```python
    spec_context: str = "none", graph: CallGraph | None = None,
```

trocar a docstring por

```python
    """``strategy="resample"`` spends the same call budget on independent samples that never see
    the previous error: the baseline a guided repair has to beat (Olausson et al., ICLR 2024).
    ``spec_context="callers"`` shows the call sites and usage facts and rejects a spec they contradict;
    ``graph`` is the repository's call graph (scan mode), else the callers come from ``source`` alone."""
```

depois da validação de `strategy`:

```python
    if spec_context not in SPEC_CONTEXTS:
        raise ValueError(f"spec_context must be one of {SPEC_CONTEXTS}")
```

antes de `work_dir.mkdir(parents=True, exist_ok=True)`:

```python
    facts = collect_facts(h, grounded, source, graph=graph) if spec_context == "callers" else None
    context = render_section(facts, grounded) if facts is not None else ""
    if facts is not None:
        result.spec_context = {"call_sites": facts.site_count, "references": len(facts.references),
                               "chars": len(context)}
```

a chamada ao LLM passa a ser

```python
        reply = llm.complete(SYSTEM_PROMPT, _user_prompt(grounded, shown_previous, shown_feedback, context),
                             json_mode=True)
```

e, dentro do `try`, logo depois de `problems = spec_problems(spec, grounded)`:

```python
            if not problems and facts is not None:
                problems = usage_problems(spec, grounded, facts)
```

`run_verify` não muda: ele já repassa `**kwargs` a `verify_hypothesis`.

- [ ] **Passo 4: rodar e ver passar.**

Run: `.venv/bin/python -m pytest tests/test_verify_loop.py tests/test_verify_caller_facts.py tests/test_verify_usage_problems.py -q`
Expected: todos passam (o arquivo do laço leva perto de 40 s por causa dos testes antigos que geram pytest).

- [ ] **Passo 5: ponto de parada (sem commit).**

---

### Tarefa 5: CLI, prompt de sistema, fingerprint e modo scan

**Files:**
- Modify: `src/main.py`
- Modify: `src/research_pipeline/prompts/input_spec_prompt.txt`
- Test: `tests/test_verify_cli.py`, `tests/test_scan_pipeline.py`

**Interfaces:**
- Consumes: `verify_hypothesis(..., spec_context, graph)` (Tarefa 4), via `run_verify(**kwargs)` e `execute_scan(**verify_kwargs)`.
- Produces: flag `--spec-context {none,callers}` (padrão `callers`); `config["spec_context"]` no fingerprint V2; `execute_scan(..., spec_context=args.spec_context, graph=plan.graph)`.

- [ ] **Passo 1: testes que falham.** Acrescentar ao fim de `tests/test_verify_cli.py`:

```python


def test_spec_context_defaults_to_callers_and_enters_the_fingerprint(tmp_path: Path, monkeypatch) -> None:
    detection = tmp_path / "sample.py"
    detection.write_text("def helper(v):\n    return v\n\n\ndef divide(x, y):\n    return helper(x) // y\n\n\n"
                         "def run():\n    return divide(1, 0)\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _SpecLLM)
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc)
    monkeypatch.setattr(loop, "concrete_replay",
                        lambda program, function, **_: ReplayVerdict("reproduced", "ZeroDivisionError", 6))
    reports = {}
    for flag in ("callers", "none"):
        out = tmp_path / flag
        args = main.build_parser().parse_args(["--mode", "hybrid", "--input", str(detection), "--output-dir",
                                               str(out), "--esbmc-command", "esbmc", "--spec-context", flag])
        assert main.mode_v2(args) == 0
        checkpoint = json.loads((out / "v2_checkpoint.json").read_text(encoding="utf-8"))
        assert checkpoint["fingerprint"]["config"]["spec_context"] == flag
        results = json.loads((out / "v2_verify_report.json").read_text(encoding="utf-8"))["results"]
        reports[flag] = next(r for r in results if r["verdict"] == "CONFIRMED")
    assert reports["callers"]["spec_context"]["call_sites"] == 1
    assert "spec_context" not in reports["none"]
    assert main.build_parser().parse_args(["--mode", "hybrid", "--input", str(detection)]).spec_context == "callers"
```

Em `tests/test_scan_pipeline.py`, em `test_cli_with_yes_runs_detection_and_verify`, logo depois de
`assert calls[0]["kwargs"]["bound"] == 9 and calls[0]["kwargs"]["esbmc_command"] == ["esbmc"]`:

```python
    assert calls[0]["kwargs"]["spec_context"] == "callers"
    assert "calc:ratio" in calls[0]["kwargs"]["graph"].functions
```

- [ ] **Passo 2: rodar e ver falhar.**

Run: `.venv/bin/python -m pytest tests/test_verify_cli.py tests/test_scan_pipeline.py -q`
Expected: 2 falhas: `SystemExit: 2` (argparse não conhece `--spec-context`) e `KeyError: 'spec_context'` no teste do scan.

- [ ] **Passo 3: implementar.** Em `src/main.py`, antes do `parser.add_argument(` de `"--verification-sources",`:

```python
    parser.add_argument(
        "--spec-context",
        choices=["none", "callers"],
        default="callers",
        help="Motor verify: 'callers' mostra ao LLM do spec as chamadas da função e os fatos de uso das entradas, "
             "e rejeita tipo contrariado pelo uso; 'none' é o pedido de antes (linha de base).",
    )
```

Na chamada `run_verify(...)` de `_mode_v2_verify`, depois de `strategy=args.spec_strategy,`:

```python
            spec_context=args.spec_context,
```

Na chamada `execute_scan(...)` de `mode_scan`, trocar `strategy=args.spec_strategy)` por:

```python
                              strategy=args.spec_strategy, spec_context=args.spec_context, graph=plan.graph)
```

No dicionário `config` de `mode_v2`, depois de `"spec_strategy": args.spec_strategy,`:

```python
        "spec_context": args.spec_context,
```

Em `src/research_pipeline/prompts/input_spec_prompt.txt`, antes da última linha
(`- When a previous attempt is shown with an error, change only what the error points to.`):

```
- Call sites and facts read from the code, when shown, are evidence: give each input a type that
  agrees with what the callers pass and with how the function uses it. An input whose methods are
  called, or that is subscripted or iterated, cannot be int, float or bool; a spec that contradicts
  that use is rejected.
```

- [ ] **Passo 4: rodar e ver passar.**

Run: `.venv/bin/python -m pytest tests/test_verify_cli.py tests/test_scan_pipeline.py -q`
Expected: todos passam.

- [ ] **Passo 5: ponto de parada (sem commit).** Lembrar à Fernanda: a partir daqui a rodada pausada em `artifacts/v2/final-2026-10-15-codex` recusa `--resume` com "configuração, prompt ou fontes mudaram".

---

### Tarefa 6: suíte completa, lint e registro

**Files:**
- Modify: `docs/historico/PLANO_GERAL_2026-10-15.md`
- Modify: `docs/experimentos/README.md`

**Interfaces:**
- Consumes: tudo das Tarefas 1 a 5. Não produz código.

- [ ] **Passo 1: suíte completa.**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha nova em relação à suíte antes da Tarefa 1 (anotar o número de testes antes e depois; o depois tem 24 a mais).

- [ ] **Passo 2: lint dos arquivos tocados.**

Run: `.venv/bin/python -m ruff check --line-length 120 src/research_pipeline/verify/caller_facts.py src/research_pipeline/scan/callgraph.py src/research_pipeline/scan/context.py tests/test_verify_caller_facts.py tests/test_verify_usage_problems.py`
Expected: `All checks passed!` (o `I001` que já existe em `loop.py` antes deste item não é deste item).

- [ ] **Passo 3: registrar.** Em `docs/historico/PLANO_GERAL_2026-10-15.md`, trocar a linha da tabela
`| 3 | Spec com contexto dos chamadores | a fazer |` por
`| 3 | Spec com contexto dos chamadores | feito (sem medição; mede no item 6) |`, e no fim da seção
`## 3. Spec com contexto dos chamadores` acrescentar:

```markdown
- [x] Spec `docs/desenho/specs/2026-10-16-spec-com-contexto-design.md`, plano
  `docs/desenho/planos/2026-10-16-spec-com-contexto.md`.
- [x] `--spec-context callers` (padrão) mostra chamadas, referências e fatos de uso ao LLM do spec e
  rejeita tipo contrariado pelo uso; `--spec-context none` é a linha de base para o item 6.
- Retomada: o prompt do spec mudou, então rodadas V2 anteriores não retomam com este código.
```

Em `docs/experimentos/README.md`, acrescentar no fim uma entrada no formato das outras, com data,
"Objetivo: item 3 do plano geral, sem rodada", "Commit: (o da Fernanda, se ela commitar)", o comando
da suíte do Passo 1 e o número de testes que passaram, e a frase "Medição adiada para o item 6
(`--spec-context none` contra `callers`)".

- [ ] **Passo 4: ponto de parada (sem commit).** Entregar à Fernanda o diff e o número da suíte.
