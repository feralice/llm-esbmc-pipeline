# Sondas de capacidade do ESBMC: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** cada regra de reescrita do harness que existe só por limitação do ESBMC-Python passa a ser ligada ou desligada por sondas (programas mínimos) rodadas no ESBMC configurado antes de cada lote, com cache por binário, flags e versão; inclui aplicar o patch das três regras pós-congelamento.

**Architecture:** `verify/rules.py` nomeia as 12 regras; as funções de reescrita (`compat.py`, `render.py`, `grounding.py`) recebem o conjunto ativo com padrão `ALL_RULES`; `verify/capabilities.py` tem o catálogo de 26 sondas (`verify/probes/*.py`), roda cada sonda pelo `check()` do motor, classifica em aceita/recusa/indeterminada, guarda o resultado em `artifacts/esbmc_capabilities/<chave>.json` e devolve o conjunto ativo; `main._mode_v2_verify` chama `resolve_rules` uma vez por lote e grava o relatório no checkpoint e em `config.capabilities`.

**Tech Stack:** Python 3.12 do `.venv`, `ast`, `hashlib`, `subprocess`, pytest; ESBMC só no teste de integração opcional.

**Spec:** `docs/superpowers/specs/2026-10-16-sondas-capacidade-design.md`

## Global Constraints

- Padrão de toda função alterada: `rules=ALL_RULES` (comportamento de hoje). Nenhum teste existente muda.
- Uma regra só desliga quando todas as suas sondas dão `aceita`; qualquer outra coisa a mantém ligada.
- Exceção só conta quando o ESBMC a nomeia; `NULL pointer` e `out-of-bounds` nunca contam.
- Nenhum teste da suíte rápida roda o ESBMC; o único que roda fica em `tests/test_verify_esbmc_integration.py`, com `skipif`.
- Não mexer em `docs/projeto/possiveis_problemas/`; as sondas são cópias.
- Sem travessão em texto; sem commit sem a Fernanda pedir (os passos de commit viram "ponto de parada").
- Trabalhar direto em `master` (regra do repo).
- Teste de um arquivo: `.venv/bin/python -m pytest tests/<arquivo> -q`. Suíte rápida: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`.

## Review Focus

- Sonda aceita por mensagem de memória (`dereference failure: NULL pointer` quando o comando não tem `--no-pointer-check`) desligaria a guarda de atributo: `named_exceptions` estrito (teste `NULL` na Tarefa 5).
- Sonda quebrada (programa que não levanta nada no CPython, ou `%` modelado como string arbitrária) desligaria uma regra à toa: checagem de cada sonda no CPython e par de sondas de `%` (Tarefa 4).
- Timeout, crash, ESBMC ausente ou exceção no mecanismo desligando regra ou parando o lote: indeterminada e `resolve_rules` com tudo ligado (Tarefas 5 e 6).
- Cache velho depois de recompilar o ESBMC atrás do mesmo `esbmc.sh`, ou com flags diferentes: a chave inclui o hash do binário que o wrapper nomeia e o comando (Tarefa 6).
- Lote retomado com regras diferentes nas duas metades: o conjunto fica no checkpoint e a retomada não sonda de novo (Tarefa 7); checkpoint antigo com resultados segue com tudo ligado (Tarefa 6).

---

### Tarefa 1: aplicar o patch das regras pós-congelamento

**Files:**
- Modify: `src/research_pipeline/verify/compat.py`, `src/research_pipeline/verify/render.py`, `src/research_pipeline/verify/pytest_gen.py` (pelo patch)
- Test: `tests/test_verify_compat.py` (pelo patch)

**Interfaces:**
- Consumes: `docs/projeto/regras_pos_congelamento_2026-10-15.patch` (base: `compat.py` 1552903, `render.py` 6de09c9, `pytest_gen.py` 228138b, `tests/test_verify_compat.py` eee11a8; `git apply --check` passou em 16/10/2026).
- Produces: `drop_project_decorators(source: str) -> tuple[str, list[str]]`; `split_conditional_assignments(source: str) -> tuple[str, list[str]]`; `_unused_definitions` ignora autorreferência; `pytest_gen._source_without_driver(source: str) -> list[str]`; `render_program` devolve `target_range` do código reescrito quando a separação acrescenta linhas.

O código desta tarefa é o próprio patch, versionado no repo; ele não é reescrito aqui. Conteúdo: em `compat.py`, `_unused_definitions` passa a registrar quem carrega cada nome (uma definição que só se nomeia não conta como usada), mais as funções `drop_project_decorators` e `split_conditional_assignments`; em `render.py`, as duas funções entram depois de `rewrite_compat` e o intervalo do alvo é recalculado quando a separação acrescenta linhas; em `pytest_gen.py`, o driver é achado pelo nome `_esbmc_main`; em `tests/test_verify_compat.py`, três testes novos.

- [ ] **Passo 1: conferir que o patch aplica**

Run: `git apply --check docs/projeto/regras_pos_congelamento_2026-10-15.patch`
Expected: nenhuma saída, código 0.

- [ ] **Passo 2: aplicar só os testes**

Run: `git apply --include='tests/test_verify_compat.py' docs/projeto/regras_pos_congelamento_2026-10-15.patch`
Expected: nenhuma saída.

- [ ] **Passo 3: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_compat.py -q`
Expected: FAIL na coleta com `ImportError: cannot import name 'drop_project_decorators' from 'research_pipeline.verify.compat'`.

- [ ] **Passo 4: aplicar o resto do patch**

Run: `git apply --exclude='tests/test_verify_compat.py' docs/projeto/regras_pos_congelamento_2026-10-15.patch`
Expected: nenhuma saída.

- [ ] **Passo 5: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_compat.py tests/test_verify_render.py -q`
Expected: PASS, incluindo `test_project_decorators_are_blanked_and_builtin_ones_stay`, `test_conditional_assignment_of_functions_becomes_if_else` e `test_a_definition_named_only_by_itself_is_unused`.

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: 0 failed.

- [ ] **Passo 6: ponto de parada (sem commit)**

---

### Tarefa 2: nomes das regras e chaves em `compat.py`

**Files:**
- Create: `src/research_pipeline/verify/rules.py`
- Modify: `src/research_pipeline/verify/compat.py`
- Test: `tests/test_verify_compat.py`

**Interfaces:**
- Consumes: `rewrite_compat(source, *, parameter_types=None)`, `none_guards(source, function, spans, never_none=frozenset())`, `_guarded_values(evaluated, names, receiver)` (Tarefa 1).
- Produces: constantes `PERCENT_FORMAT`, `METHOD_ALIAS`, `BUILTIN_NAMED_METHODS`, `PROPERTIES_AS_ATTRIBUTES`, `PROJECT_DECORATORS`, `CONDITIONAL_ASSIGNMENTS`, `NONE_ATTRIBUTE`, `NONE_SUBSCRIPT`, `NONE_CALL`, `NONE_MEMBERSHIP`, `NONE_ORDERING`, `NONE_ARITHMETIC`, `NONE_GUARD_KINDS: frozenset[str]`, `ALL_RULES: frozenset[str]`; `rewrite_compat(source: str, *, parameter_types: dict[str, dict[str, str]] | None = None, rules: frozenset[str] = ALL_RULES) -> tuple[str, list[str]]`; `none_guards(source: str, function: str, spans: tuple[tuple[int, int], ...], never_none: frozenset[str] | set[str] = frozenset(), kinds: frozenset[str] = NONE_GUARD_KINDS) -> tuple[str, list[str]]`; `_guarded_values(...) -> list[tuple[ast.expr, str, str]]` (valor, helper, regra).

- [ ] **Passo 1: testes que falham**

No bloco de imports do topo de `tests/test_verify_compat.py`, acrescentar:

```python
from research_pipeline.verify.rules import (
    ALL_RULES,
    METHOD_ALIAS,
    NONE_ATTRIBUTE,
    NONE_GUARD_KINDS,
    PERCENT_FORMAT,
)
```

Acrescentar ao fim do mesmo arquivo:

```python
def test_rule_names_cover_every_none_guard_kind():
    assert NONE_GUARD_KINDS < ALL_RULES and len(ALL_RULES) == 12


def test_rewrite_compat_skips_a_disabled_percent_rule():
    source = 'def label(code, name):\n    return "id=%s:%s!" % (code, name)\n'
    types = {"label": {"code": "int", "name": "str"}}
    assert rewrite_compat(source, parameter_types=types, rules=ALL_RULES - {PERCENT_FORMAT}) == (source, [])
    assert rewrite_compat(source, parameter_types=types)[1] == ["compat_percent_format:1"]


def test_rewrite_compat_skips_a_disabled_alias_rule():
    source = "class C:\n    def __str__(self):\n        return 'c'\n    __repr__ = __str__\n"
    assert rewrite_compat(source, rules=ALL_RULES - {METHOD_ALIAS}) == (source, [])
    assert rewrite_compat(source)[1] == ["compat_method_alias:1"]


def test_none_guards_keep_only_the_enabled_kinds():
    source = "def f(a, xs):\n    y = a.size, 'k' in xs\n    return y\n"
    both, transforms = none_guards(source, "f", ((2, 2),))
    assert "_esbmc_none_attribute(a is None)" in both and "_esbmc_none_type(xs is None)" in both
    assert transforms == ["none_guards:2"]
    only_in, transforms = none_guards(source, "f", ((2, 2),), kinds=NONE_GUARD_KINDS - {NONE_ATTRIBUTE})
    assert "_esbmc_none_attribute" not in only_in and "_esbmc_none_type(xs is None)" in only_in
    assert transforms == ["none_guards:1"]
    assert none_guards(source, "f", ((2, 2),), kinds=frozenset()) == (source, [])
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_compat.py -q`
Expected: FAIL na coleta com `ModuleNotFoundError: No module named 'research_pipeline.verify.rules'`.

- [ ] **Passo 3: implementação mínima**

Criar `src/research_pipeline/verify/rules.py`:

```python
"""Harness rewrites that exist only because ESBMC-Python refuses or mis-models a construct.

Each id is the transform the pipeline reports (``none_guards`` is split by construct);
capabilities.py probes the installed ESBMC and switches a rule off once ESBMC handles it."""

from __future__ import annotations

PERCENT_FORMAT = "compat_percent_format"
METHOD_ALIAS = "compat_method_alias"
BUILTIN_NAMED_METHODS = "builtin_named_methods_renamed"
PROPERTIES_AS_ATTRIBUTES = "properties_as_attributes"
PROJECT_DECORATORS = "project_decorators_removed"
CONDITIONAL_ASSIGNMENTS = "conditional_assignments_split"
NONE_ATTRIBUTE = "none_guards_attribute"
NONE_SUBSCRIPT = "none_guards_subscript"
NONE_CALL = "none_guards_call"
NONE_MEMBERSHIP = "none_guards_membership"
NONE_ORDERING = "none_guards_ordering"
NONE_ARITHMETIC = "none_guards_arithmetic"

NONE_GUARD_KINDS = frozenset({NONE_ATTRIBUTE, NONE_SUBSCRIPT, NONE_CALL, NONE_MEMBERSHIP, NONE_ORDERING,
                              NONE_ARITHMETIC})
ALL_RULES = frozenset({PERCENT_FORMAT, METHOD_ALIAS, BUILTIN_NAMED_METHODS, PROPERTIES_AS_ATTRIBUTES,
                       PROJECT_DECORATORS, CONDITIONAL_ASSIGNMENTS, *NONE_GUARD_KINDS})
```

Em `src/research_pipeline/verify/compat.py`, trocar a linha `from .astutil import find_function` por:

```python
from .astutil import find_function
from .rules import (
    ALL_RULES,
    METHOD_ALIAS,
    NONE_ARITHMETIC,
    NONE_ATTRIBUTE,
    NONE_CALL,
    NONE_GUARD_KINDS,
    NONE_MEMBERSHIP,
    NONE_ORDERING,
    NONE_SUBSCRIPT,
    PERCENT_FORMAT,
)
```

Trocar o começo de `rewrite_compat` (assinatura até a linha `aliases = ...`) por:

```python
def rewrite_compat(source: str, *, parameter_types: dict[str, dict[str, str]] | None = None,
                   rules: frozenset[str] = ALL_RULES) -> tuple[str, list[str]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, []
    percent = _percent_format_edits(tree, parameter_types or {}) if PERCENT_FORMAT in rules else []
    aliases = _method_alias_edits(tree) if METHOD_ALIAS in rules else []
```

Trocar `_guarded_values` inteira por:

```python
def _guarded_values(evaluated: list[ast.AST], names: set[str], receiver: str | None) -> list[tuple[ast.expr, str, str]]:
    """(value, helper, rule) for each value CPython rejects when it is None."""
    def _chain(node: ast.expr) -> bool:
        return _is_chain(node, names, receiver)

    found: list[tuple[ast.expr, str, str]] = []
    for node in evaluated:
        if isinstance(node, ast.Attribute) and _chain(node.value):
            found.append((node.value, "_esbmc_none_attribute", NONE_ATTRIBUTE))
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Load) and _chain(node.value):
            found.append((node.value, "_esbmc_none_type", NONE_SUBSCRIPT))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in _TYPE_CALLS \
                and len(node.args) == 1 and _chain(node.args[0]):
            found.append((node.args[0], "_esbmc_none_type", NONE_CALL))
        elif isinstance(node, ast.Compare):
            op, right = node.ops[0], node.comparators[0]
            if isinstance(op, (ast.In, ast.NotIn)) and _chain(right):
                found.append((right, "_esbmc_none_type", NONE_MEMBERSHIP))
            elif isinstance(op, _ORDERING):
                found += [(side, "_esbmc_none_type", NONE_ORDERING) for side in (node.left, right) if _chain(side)]
        elif isinstance(node, ast.BinOp) and isinstance(node.op, _ARITHMETIC):
            found += [(side, "_esbmc_none_type", NONE_ARITHMETIC) for side in (node.left, node.right) if _chain(side)]
    return found
```

Em `none_guards`, trocar a assinatura por:

```python
def none_guards(source: str, function: str, spans: tuple[tuple[int, int], ...],
                never_none: frozenset[str] | set[str] = frozenset(),
                kinds: frozenset[str] = NONE_GUARD_KINDS) -> tuple[str, list[str]]:
```

e trocar o laço que monta `calls` por:

```python
    calls: list[str] = []
    for value, helper, rule in values:
        call = f"{helper}({ast.unparse(value)} is None)"
        if rule in kinds and ast.unparse(value) not in never_none and call not in calls:
            calls.append(call)
```

Acrescentar ao docstring de `none_guards` a frase: `` ``kinds`` names the rules (rules.NONE_GUARD_KINDS) whose guards are kept.``

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_compat.py tests/test_verify_compat_boundary.py tests/test_verify_render.py -q`
Expected: PASS.

- [ ] **Passo 5: ponto de parada (sem commit)**

---

### Tarefa 3: regras em `render_program`, `ground` e no laço

**Files:**
- Modify: `src/research_pipeline/verify/render.py`, `src/research_pipeline/verify/grounding.py`, `src/research_pipeline/verify/loop.py`
- Test: `tests/test_verify_render.py`, `tests/test_verify_grounding.py`, `tests/test_verify_loop.py`

**Interfaces:**
- Consumes: `rules.py` e as assinaturas novas de `rewrite_compat`/`none_guards` (Tarefa 2); `drop_project_decorators`, `split_conditional_assignments` (Tarefa 1).
- Produces: `render_program(grounded: Grounded, spec: InputSpec, rules: frozenset[str] = ALL_RULES) -> Program`; `ground(h: BugHypothesis, source: str, refused: frozenset[str] = frozenset(), rules: frozenset[str] = ALL_RULES) -> Grounded | GroundingFailure`; `precheck(h: BugHypothesis, source: str, esbmc_command: list[str] | None = None, rules: frozenset[str] = ALL_RULES) -> tuple[Grounded | None, str, str]`; `verify_hypothesis(..., rules: frozenset[str] = ALL_RULES) -> VerifyResult`; em `grounding.py`, `_replaced(cls, start, replace_properties: bool) -> set[str]` e o parâmetro `replace_properties: bool = True` em `_loaded_self_attrs`, `_receiver_attrs`, `_called_attrs`, `_inherited_reads`.

- [ ] **Passo 1: testes que falham**

No bloco de imports do topo de `tests/test_verify_render.py`, acrescentar:

```python
from research_pipeline.verify.rules import ALL_RULES, BUILTIN_NAMED_METHODS, NONE_GUARD_KINDS
```

Acrescentar ao fim do mesmo arquivo:

```python
STORE = "class Store:\n    def get(self, k):\n        return 10 // k\n"


def test_builtin_named_rule_off_keeps_the_method_name():
    grounded = ground(BugHypothesis("x.py", "Store.get", "10 // k"), STORE)
    spec = InputSpec({"k": "int"}, {}, ())
    full = render_program(grounded, spec)
    assert "def esbmc_get(" in full.source
    assert any(t.startswith("builtin_named_methods_renamed") for t in full.transforms)
    plain = render_program(grounded, spec, rules=ALL_RULES - {BUILTIN_NAMED_METHODS})
    assert "def get(self, k: int)" in plain.source and "_receiver.get(k)" in plain.source
    assert not any(t.startswith("builtin_named_methods_renamed") for t in plain.transforms)


def test_none_guards_follow_the_enabled_rules():
    grounded = _ground("ratio", "total // count")
    spec = InputSpec({"total": "Optional[int]", "count": "int"}, {}, ())
    assert "_esbmc_none_type(total is None)" in render_program(grounded, spec).source
    off = render_program(grounded, spec, rules=ALL_RULES - NONE_GUARD_KINDS)
    assert "_esbmc_none_type" not in off.source
    assert not any(t.startswith("none_guards") for t in off.transforms)
```

No bloco de imports do topo de `tests/test_verify_grounding.py`, acrescentar:

```python
from research_pipeline.verify.rules import ALL_RULES, PROPERTIES_AS_ATTRIBUTES
```

Acrescentar ao fim do mesmo arquivo:

```python
def test_properties_stay_when_the_rule_is_off():
    result = ground(_h("Request.follow", "self.url[n]"), PROPERTY_SOURCE,
                    rules=ALL_RULES - {PROPERTIES_AS_ATTRIBUTES})
    assert isinstance(result, Grounded) and result.unsupported == ""
    assert set(result.receiver_attrs) == {"_url", "_body"}
    assert "@property" in result.module and "url = property(_get_url)" in result.module
    assert not any(t.startswith("properties_as_attributes") for t in result.transforms)
```

Acrescentar `import pytest` ao topo de `tests/test_verify_loop.py` (o arquivo ainda não importa) e, ao fim:

```python
def test_rules_reach_grounding_and_both_renders(tmp_path, monkeypatch):
    rules = frozenset({"compat_percent_format"})
    seen = []
    real_ground, real_render = loop.ground, loop.render_program

    class Stop(Exception):
        pass

    def spy_ground(h, source, refused=frozenset(), rules=None):
        seen.append(("ground", rules))
        return real_ground(h, source, refused, rules)

    def spy_render(grounded, spec, rules=None):
        seen.append(("render", rules))
        if sum(1 for step, _ in seen if step == "render") == 2:
            raise Stop
        return real_render(grounded, spec, rules)

    monkeypatch.setattr(loop, "ground", spy_ground)
    monkeypatch.setattr(loop, "render_program", spy_render)
    hypothesis = BugHypothesis("r.py", "ratio", "total // count")
    with pytest.raises(Stop):
        loop.verify_hypothesis(hypothesis, llm=FakeLLM([GOOD]), source=SOURCE, esbmc_command=None, bound=5,
                               timeout_seconds=30, work_dir=tmp_path, rules=rules)
    assert seen == [("ground", rules), ("render", rules), ("render", rules)]
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_render.py tests/test_verify_grounding.py tests/test_verify_loop.py -q`
Expected: FAIL com `TypeError: render_program() got an unexpected keyword argument 'rules'`, `TypeError: ground() got an unexpected keyword argument 'rules'` e `TypeError: verify_hypothesis() got an unexpected keyword argument 'rules'`.

- [ ] **Passo 3: implementação mínima**

Em `src/research_pipeline/verify/render.py`, depois do bloco `from .grounding import Grounded`, acrescentar:

```python
from .rules import ALL_RULES, BUILTIN_NAMED_METHODS, CONDITIONAL_ASSIGNMENTS, NONE_GUARD_KINDS, PROJECT_DECORATORS
```

Trocar a assinatura de `render_program` por:

```python
def render_program(grounded: Grounded, spec: InputSpec, rules: frozenset[str] = ALL_RULES) -> Program:
```

Trocar o bloco que começa em `rewritten, compat = rewrite_compat(` e vai até a linha `rewritten, guards = none_guards(...)` (inclusive) por:

```python
    rewritten, compat = rewrite_compat(body, parameter_types={grounded.hypothesis.function: params}, rules=rules)
    rewritten, decorators = (drop_project_decorators(rewritten) if PROJECT_DECORATORS in rules
                             else (rewritten, []))
    rewritten, split = (split_conditional_assignments(rewritten) if CONDITIONAL_ASSIGNMENTS in rules
                        else (rewritten, []))
    compat += [*decorators, *split]
    if BUILTIN_NAMED_METHODS in rules:
        rewritten, target, renamed = rename_builtin_named_methods(rewritten, grounded.hypothesis.function)
    else:
        target, renamed = grounded.hypothesis.function, []
    rewritten_spans = _suspect_spans(rewritten, grounded, spans[0][0], target) or spans
    rewritten, cut = cut_after_suspect(rewritten, target, rewritten_spans)
    rewritten, unused = remove_unused(rewritten, target)
    never_none = {key for key, text in input_types(spec, grounded).items()
                  if (shape := parse_type(text)) is not None and not shape.optional and shape.kind != "none"}
    rewritten, guards = none_guards(rewritten, target, rewritten_spans, never_none, kinds=rules & NONE_GUARD_KINDS)
```

Em `src/research_pipeline/verify/grounding.py`, depois de `from .hypothesis import BugHypothesis`, acrescentar:

```python
from .rules import ALL_RULES, PROPERTIES_AS_ATTRIBUTES
```

Logo depois de `_replaced_properties`, acrescentar:

```python
def _replaced(cls: ast.ClassDef, start: str, replace_properties: bool) -> set[str]:
    return _replaced_properties(cls, start) if replace_properties else set()
```

Trocar `_loaded_self_attrs`, `_receiver_attrs`, `_called_attrs` e `_inherited_reads` inteiras por:

```python
def _loaded_self_attrs(cls: ast.ClassDef, method: str, replace_properties: bool = True) -> set[str]:
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    return {
        _self_attribute(node)
        for name in _reachable_methods(cls, method, _replaced(cls, method, replace_properties))
        for node in ast.walk(methods[name])
        if isinstance(node, ast.Attribute) and isinstance(node.ctx, ast.Load) and _self_attribute(node)
    }


def _receiver_attrs(cls: ast.ClassDef, method: str, replace_properties: bool = True) -> tuple[str, ...]:
    values = _class_level_values(cls) - _replaced(cls, method, replace_properties)
    return tuple(sorted(_loaded_self_attrs(cls, method, replace_properties) - values))


def _called_attrs(cls: ast.ClassDef, method: str, attrs: tuple[str, ...],
                  replace_properties: bool = True) -> dict[str, CallShape]:
    """Receiver attributes the reachable methods only call (``self.write(x)``): methods the class
    inherits from a library base, so the shell gives them a stub method, not a field."""
    methods = {n.name: n for n in cls.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    calls: dict[str, CallShape] = {}
    values: set[str] = set()
    for name in _reachable_methods(cls, method, _replaced(cls, method, replace_properties)):
        parents = {id(c): n for n in ast.walk(methods[name]) for c in ast.iter_child_nodes(n)}
        for node in ast.walk(methods[name]):
            attr = _self_attribute(node)
            if attr not in attrs:
                continue
            parent = parents.get(id(node))
            shape = _shape(parent) if isinstance(parent, ast.Call) and parent.func is node else None
            if shape is None:
                values.add(attr)
            else:
                calls[attr] = _merge(calls.get(attr), shape)
    return {attr: shape for attr, shape in calls.items() if attr not in values}


def _inherited_reads(tree: ast.Module, cls: ast.ClassDef, method: str, replace_properties: bool = True) -> set[str]:
    inherited = set()
    for base in cls.bases:
        base_cls = _class_of(tree, base.id) if isinstance(base, ast.Name) else None
        if base_cls is not None:
            inherited |= _class_level_values(base_cls)
    return (_loaded_self_attrs(cls, method, replace_properties) & inherited) - _class_level_values(cls)
```

Em `ground`, trocar a assinatura e acrescentar a primeira linha do corpo:

```python
def ground(h: BugHypothesis, source: str, refused: frozenset[str] = frozenset(),
           rules: frozenset[str] = ALL_RULES) -> Grounded | GroundingFailure:
    properties = PROPERTIES_AS_ATTRIBUTES in rules
    try:
        tree = ast.parse(source)
```

e, ainda em `ground`, fazer estas trocas de linha (o resto fica igual):

```python
            grounded = ground(hoisted[1], hoisted[0], refused, rules)
```
no lugar de `grounded = ground(hoisted[1], hoisted[0], refused)`;

```python
        inherited = _inherited_reads(tree, cls, function.name, properties)
```
no lugar de `inherited = _inherited_reads(tree, cls, function.name)`;

```python
            grounded = ground(h, inlined, refused, rules)
```
no lugar de `grounded = ground(h, inlined, refused)`;

```python
    receiver_attrs = _receiver_attrs(cls, function.name, properties) if entry == "method" else ()
```
no lugar de `receiver_attrs = _receiver_attrs(cls, function.name) if entry == "method" else ()`;

```python
            replaced = _replaced(cls, function.name, properties) if entry == "method" else set()
```
no lugar de `replaced = _replaced_properties(cls, function.name) if entry == "method" else set()`;

```python
        called_attrs=_called_attrs(cls, function.name, receiver_attrs, properties) if receiver_attrs else {},
```
no lugar de `called_attrs=_called_attrs(cls, function.name, receiver_attrs) if receiver_attrs else {},`.

Em `src/research_pipeline/verify/loop.py`, depois de `from .render import DRIVER, Program, RenderError, render_program`, acrescentar:

```python
from .rules import ALL_RULES
```

Trocar `precheck` inteira por:

```python
def precheck(h: BugHypothesis, source: str, esbmc_command: list[str] | None = None,
             rules: frozenset[str] = ALL_RULES) -> tuple[Grounded | None, str, str]:
    """Everything decidable before spending an LLM call; returns (grounded, "", "") when ready.
    With ``esbmc_command``, library members ESBMC cannot convert are stubbed before the LLM sees the slice."""
    refused: frozenset[str] = frozenset()
    for _ in range(_ORACLE_ROUNDS):
        grounded = ground(h, source, refused, rules=rules)
        if isinstance(grounded, GroundingFailure):
            return None, UNSUPPORTED if grounded.unsupported else GROUNDING_FAILED, grounded.reason
        try:
            probe = render_program(grounded, _placeholder_spec(grounded), rules=rules)
        except RenderError as exc:
            return None, UNSUPPORTED, str(exc)
        if not esbmc_command:
            break
        new = refusals(convert(probe.source, esbmc_command), probe.source) - refused
        if not new:
            break
        refused |= new
    undefined = undefined_globals(probe.source, "program.py") - _INTRINSICS
    if undefined:
        return None, MISSING_DEPENDENCY, "undefined name(s): " + ", ".join(sorted(undefined))
    return grounded, "", ""
```

Em `verify_hypothesis`, trocar a assinatura por:

```python
def verify_hypothesis(
    h: BugHypothesis, *, llm: SpecLLM, source: str, esbmc_command: list[str] | None, bound: int,
    timeout_seconds: int, work_dir: Path, max_repairs: int = 2, replay_runs: int = 400,
    strategy: str = "repair", rules: frozenset[str] = ALL_RULES,
) -> VerifyResult:
```

e trocar as duas chamadas:

```python
    grounded, verdict, reason = precheck(h, source, esbmc_command, rules)
```
no lugar de `grounded, verdict, reason = precheck(h, source, esbmc_command)`;

```python
        program = render_program(grounded, spec, rules=rules)
```
no lugar de `program = render_program(grounded, spec)`.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_render.py tests/test_verify_grounding.py tests/test_verify_loop.py tests/test_verify_oracle.py -q`
Expected: PASS.

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: 0 failed.

- [ ] **Passo 5: ponto de parada (sem commit)**

---

### Tarefa 4: catálogo e programas das sondas

**Files:**
- Create: `src/research_pipeline/verify/capabilities.py`
- Create: `src/research_pipeline/verify/probes/` com 26 arquivos `.py` (listados abaixo)
- Test: `tests/test_verify_capabilities.py`

**Interfaces:**
- Consumes: `rules.py` (Tarefa 2).
- Produces: `PROBE_DIR: Path`; `ACEITA`, `RECUSA`, `INDETERMINADA: str`; `@dataclass(frozen=True) class Probe(name: str, rule: str, exception: str | None, cpython: tuple[tuple[str, object], ...] = ())` com `path -> Path` e `source() -> str`; `PROBES: tuple[Probe, ...]`; `catalog_digest(probes: tuple[Probe, ...] = PROBES) -> str`.

- [ ] **Passo 1: testes que falham**

Criar `tests/test_verify_capabilities.py`:

```python
import pytest

from research_pipeline.verify.capabilities import PROBES, Probe, catalog_digest
from research_pipeline.verify.rules import ALL_RULES


class _Infeasible(Exception):
    pass


def _cpython_run(probe: Probe) -> BaseException | None:
    """Runs the probe under CPython with its declared nondet values; returns what it raised."""
    values = {"nondet_bool": False, "nondet_int": 0, "nondet_str": "", **dict(probe.cpython)}

    def assume(condition):
        if not condition:
            raise _Infeasible(probe.name)

    namespace = {name: (lambda value=value: value) for name, value in values.items()}
    namespace.update({"__ESBMC_assume": assume, "__name__": "probe"})
    try:
        exec(compile(probe.source(), str(probe.path), "exec"), namespace)
    except _Infeasible:
        raise
    except Exception as exc:  # noqa: BLE001 - the raised exception is the result under test
        return exc
    return None


def test_every_rule_has_a_probe_and_every_probe_a_known_rule():
    assert {p.rule for p in PROBES} == ALL_RULES
    assert len({p.name for p in PROBES}) == len(PROBES) == 26
    assert all(p.path.exists() for p in PROBES)


@pytest.mark.parametrize("probe", PROBES, ids=lambda p: p.name)
def test_cpython_does_what_the_probe_expects(probe):
    raised = _cpython_run(probe)
    if probe.exception is None:
        assert raised is None
    else:
        assert type(raised).__name__ == probe.exception


def test_catalog_digest_changes_with_any_probe():
    before = catalog_digest()
    last = PROBES[-1]
    changed = (*PROBES[:-1], Probe(last.name, last.rule, "ValueError", last.cpython))
    assert catalog_digest(changed) != before
    assert catalog_digest() == before
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_capabilities.py -q`
Expected: FAIL na coleta com `ModuleNotFoundError: No module named 'research_pipeline.verify.capabilities'`.

- [ ] **Passo 3: implementação mínima**

Criar `src/research_pipeline/verify/capabilities.py`:

```python
"""Capability probes: which harness rules (rules.py) the installed ESBMC still needs.

Each rule has small programs under probes/. A probe is "aceita" when ESBMC reports what CPython does
(the named exception, or no violation for a safe program). A rule is switched off only when every
probe of it is aceita; a refusal, a timeout or a crash keeps it on."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .rules import (
    BUILTIN_NAMED_METHODS,
    CONDITIONAL_ASSIGNMENTS,
    METHOD_ALIAS,
    NONE_ARITHMETIC,
    NONE_ATTRIBUTE,
    NONE_CALL,
    NONE_MEMBERSHIP,
    NONE_ORDERING,
    NONE_SUBSCRIPT,
    PERCENT_FORMAT,
    PROJECT_DECORATORS,
    PROPERTIES_AS_ATTRIBUTES,
)

PROBE_DIR = Path(__file__).resolve().parent / "probes"
ACEITA, RECUSA, INDETERMINADA = "aceita", "recusa", "indeterminada"


@dataclass(frozen=True)
class Probe:
    name: str
    rule: str
    # What CPython raises and a correct ESBMC reports; None: the program is safe.
    exception: str | None
    # Values the CPython check gives each nondet_* call (default False, 0, "").
    cpython: tuple[tuple[str, object], ...] = ()

    @property
    def path(self) -> Path:
        return PROBE_DIR / f"{self.name}.py"

    def source(self) -> str:
        return self.path.read_text(encoding="utf-8")


PROBES = (
    Probe("percent_valor", PERCENT_FORMAT, None, (("nondet_int", 7),)),
    Probe("percent_violacao", PERCENT_FORMAT, "AssertionError", (("nondet_int", 7),)),
    Probe("alias_de_metodo", METHOD_ALIAS, "ZeroDivisionError"),
    Probe("metodo_append", BUILTIN_NAMED_METHODS, "ZeroDivisionError"),
    Probe("metodo_get", BUILTIN_NAMED_METHODS, "ZeroDivisionError"),
    Probe("property_decorador", PROPERTIES_AS_ATTRIBUTES, "ZeroDivisionError"),
    Probe("property_funcao", PROPERTIES_AS_ATTRIBUTES, "ZeroDivisionError"),
    Probe("decorador_do_projeto", PROJECT_DECORATORS, "ZeroDivisionError"),
    Probe("condicional_de_funcoes", CONDITIONAL_ASSIGNMENTS, "ZeroDivisionError"),
    Probe("none_atributo_local", NONE_ATTRIBUTE, "AttributeError"),
    Probe("none_atributo_campo", NONE_ATTRIBUTE, "AttributeError"),
    Probe("none_indice_local", NONE_SUBSCRIPT, "TypeError"),
    Probe("none_indice_campo", NONE_SUBSCRIPT, "TypeError"),
    Probe("none_len_local", NONE_CALL, "TypeError"),
    Probe("none_int_local", NONE_CALL, "TypeError"),
    Probe("none_float_local", NONE_CALL, "TypeError"),
    Probe("none_int_campo", NONE_CALL, "TypeError"),
    Probe("none_in_dict_local", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_lista_local", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_str_local", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_in_str_campo", NONE_MEMBERSHIP, "TypeError"),
    Probe("none_ordem_local", NONE_ORDERING, "TypeError"),
    Probe("none_ordem_campo", NONE_ORDERING, "TypeError"),
    Probe("none_soma_local", NONE_ARITHMETIC, "TypeError"),
    Probe("none_produto_local", NONE_ARITHMETIC, "TypeError"),
    Probe("none_soma_campo", NONE_ARITHMETIC, "TypeError"),
)


def catalog_digest(probes: tuple[Probe, ...] = PROBES) -> str:
    """Changes whenever a probe, its rule, its expectation or its program changes."""
    digest = hashlib.sha256()
    for probe in sorted(probes, key=lambda p: p.name):
        digest.update(repr((probe.name, probe.rule, probe.exception, probe.cpython)).encode("utf-8"))
        digest.update(probe.source().encode("utf-8"))
    return digest.hexdigest()
```

Criar os 26 programas em `src/research_pipeline/verify/probes/`:

`percent_valor.py`:

```python
# Regra compat_percent_format. Origem: docs/projeto/possiveis_problemas/17_formatacao_percent.py.
def label(code: int, name: str) -> str:
    return "%s %d" % (name, code)


def main() -> None:
    code: int = nondet_int()
    __ESBMC_assume(code == 7)
    s: str = label(code, "ab")
    assert s == "ab 7"


main()
```

`percent_violacao.py`:

```python
# Regra compat_percent_format. Origem: docs/projeto/possiveis_problemas/17_formatacao_percent.py.
def label(code: int, name: str) -> str:
    return "%s %d" % (name, code)


def main() -> None:
    code: int = nondet_int()
    __ESBMC_assume(code == 7)
    s: str = label(code, "ab")
    assert s != "ab 7"


main()
```

`alias_de_metodo.py`:

```python
# Regra compat_method_alias. Sonda nova: o 8.5 recusava "__repr__ = __str__" ("Variable __str__ not found").
class Box:
    def __init__(self) -> None:
        self.k: int = 0

    def ratio(self) -> int:
        return 10 // self.k

    share = ratio


def main() -> None:
    b = Box()
    b.share()


main()
```

`metodo_append.py`:

```python
# Regra builtin_named_methods_renamed. Origem: docs/projeto/possiveis_problemas/27_metodo_append_do_usuario.py.
class Store:
    def __init__(self) -> None:
        self.n: int = 0

    def append(self, k: int) -> int:
        return 10 // k


def main() -> None:
    s = Store()
    s.append(0)


main()
```

`metodo_get.py`:

```python
# Regra builtin_named_methods_renamed. Origem: variante get do 27 ("Dictionary variable not found").
class Codes:
    def __init__(self) -> None:
        self.n: int = 0

    def get(self, k: int) -> int:
        return 10 // k


def main() -> None:
    c = Codes()
    c.get(0)


main()
```

`property_decorador.py`:

```python
# Regra properties_as_attributes. Sonda nova: o 8.5 não tinha property.
class Account:
    def __init__(self) -> None:
        self.total: int = 0

    @property
    def share(self) -> int:
        return 10 // self.total


def main() -> None:
    a = Account()
    x = a.share


main()
```

`property_funcao.py`:

```python
# Regra properties_as_attributes. Sonda nova: forma share = property(_share).
class Account:
    def __init__(self) -> None:
        self.total: int = 0

    def _share(self) -> int:
        return 10 // self.total

    share = property(_share)


def main() -> None:
    a = Account()
    x = a.share


main()
```

`decorador_do_projeto.py`:

```python
# Regra project_decorators_removed. Origem: docs/projeto/regras_pos_congelamento_2026-10-15.patch.
def logged(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@logged
def ratio(k: int) -> int:
    return 10 // k


def main() -> None:
    ratio(0)


main()
```

`condicional_de_funcoes.py`:

```python
# Regra conditional_assignments_split. Origem: docs/projeto/regras_pos_congelamento_2026-10-15.patch.
def scale(c: int, w: int) -> int:
    return 10 // w


def main() -> None:
    a: int = nondet_int()
    g = scale if a == 1 else (lambda c, w: scale(c, w))
    g(1, 0)


main()
```

`none_atributo_local.py`:

```python
# Regra none_guards_attribute. Origem: docs/projeto/possiveis_problemas/01_methNone.py.
from typing import Optional


class Ex:
    def shutdown(self) -> None:
        pass


def main() -> None:
    e: Optional[Ex] = None
    if nondet_bool():
        e = Ex()
    e.shutdown()


main()
```

`none_atributo_campo.py`:

```python
# Regra none_guards_attribute. Origem: docs/projeto/possiveis_problemas/25_atributo_em_none.py.
from typing import Optional


class Node:
    def __init__(self) -> None:
        self.nxt: Optional[Node] = None
        self.val: int = 0


def main() -> None:
    a = Node()
    if nondet_bool():
        a.nxt = Node()
    x = a.nxt.val


main()
```

`none_indice_local.py`:

```python
# Regra none_guards_subscript. Sonda nova.
from typing import Optional


def main() -> None:
    xs: Optional[list[int]] = None
    if nondet_bool():
        xs = [1]
    y = xs[0]


main()
```

`none_indice_campo.py`:

```python
# Regra none_guards_subscript. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.xs: Optional[list[int]] = None
        if nondet_bool():
            self.xs = [1]


def main() -> None:
    b = Box()
    y = b.xs[0]


main()
```

`none_len_local.py`:

```python
# Regra none_guards_call. Sonda nova.
from typing import Optional


def main() -> None:
    xs: Optional[list[int]] = None
    if nondet_bool():
        xs = [1]
    n = len(xs)


main()
```

`none_int_local.py`:

```python
# Regra none_guards_call. Origem: docs/projeto/possiveis_problemas/39_int_de_none.py.
from typing import Optional


def main() -> None:
    status: Optional[str] = None
    if nondet_bool():
        status = "7"
    code = int(status)


main()
```

`none_float_local.py`:

```python
# Regra none_guards_call. Sonda nova.
from typing import Optional


def main() -> None:
    v: Optional[str] = None
    if nondet_bool():
        v = "1.5"
    f = float(v)


main()
```

`none_int_campo.py`:

```python
# Regra none_guards_call. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.status: Optional[str] = None
        if nondet_bool():
            self.status = "7"


def main() -> None:
    b = Box()
    code = int(b.status)


main()
```

`none_in_dict_local.py`:

```python
# Regra none_guards_membership. Origem: docs/projeto/possiveis_problemas/04_inNone.py.
from typing import Optional


def f(classes: Optional[dict], tag: str) -> bool:
    return tag in classes


def main() -> None:
    classes: Optional[dict] = None
    if nondet_bool():
        classes = {"pre": "x"}
    f(classes, "pre")


main()
```

`none_in_lista_local.py`:

```python
# Regra none_guards_membership. Sonda nova.
from typing import Optional


def main() -> None:
    xs: Optional[list[str]] = None
    if nondet_bool():
        xs = ["a"]
    found = "a" in xs


main()
```

`none_in_str_local.py`:

```python
# Regra none_guards_membership. Origem: docs/projeto/possiveis_problemas/26_in_str_none.py.
from typing import Optional


def main() -> None:
    s: Optional[str] = None
    if nondet_bool():
        s = "xy"
    found = "ab" in s


main()
```

`none_in_str_campo.py`:

```python
# Regra none_guards_membership. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.s: Optional[str] = None
        if nondet_bool():
            self.s = "xy"


def main() -> None:
    b = Box()
    found = "ab" in b.s


main()
```

`none_ordem_local.py`:

```python
# Regra none_guards_ordering. Origem: docs/projeto/possiveis_problemas/03_ge.py.
from typing import Optional


def f(limit: Optional[int], n: int) -> bool:
    return n >= limit


def main() -> None:
    limit: Optional[int] = None
    if nondet_bool():
        limit = 5
    r: bool = f(limit, 3)
    assert r or not r


main()
```

`none_ordem_campo.py`:

```python
# Regra none_guards_ordering. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.limit: Optional[int] = None
        if nondet_bool():
            self.limit = 5


def main() -> None:
    b = Box()
    r: bool = 3 >= b.limit


main()
```

`none_soma_local.py`:

```python
# Regra none_guards_arithmetic. Origem: docs/projeto/possiveis_problemas/10_optional_soma_falso_negativo.py.
from typing import Optional


def inc(v: Optional[int]) -> int:
    return v + 1


def main() -> None:
    v: Optional[int] = None
    if nondet_bool():
        v = nondet_int()
    inc(v)


main()
```

`none_produto_local.py`:

```python
# Regra none_guards_arithmetic. Origem: docs/projeto/possiveis_problemas/02_mul.py.
from typing import Optional


def f(t: Optional[int], s: int) -> int:
    return t * s


def main() -> None:
    t: Optional[int] = None
    if nondet_bool():
        t = 5
    r: int = f(t, 2)
    assert r != -7777


main()
```

`none_soma_campo.py`:

```python
# Regra none_guards_arithmetic. Sonda nova.
from typing import Optional


class Box:
    def __init__(self) -> None:
        self.v: Optional[int] = None
        if nondet_bool():
            self.v = 3


def main() -> None:
    b = Box()
    x = b.v + 1


main()
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_capabilities.py -q`
Expected: PASS (28 testes: 26 sondas no CPython, catálogo e digest).

- [ ] **Passo 5: ponto de parada (sem commit)**

---

### Tarefa 5: rodar e classificar uma sonda; regras ativas

**Files:**
- Modify: `src/research_pipeline/verify/capabilities.py`
- Test: `tests/test_verify_capabilities.py`

**Interfaces:**
- Consumes: `check(path, *, esbmc_command, bound, timeout_seconds, work_dir, runner=None) -> tuple[ESBMCDirectResult, EsbmcReading, dict]` e `Runner` (`esbmc_run.py`); `EsbmcReading.kind` em `violation | artifact | safe | repairable | missing_dependency | timeout | error` (`outcome.py`); `PROBES`, `ALL_RULES`.
- Produces: `named_exceptions(properties: list[object]) -> frozenset[str]`; `classify_probe(probe: Probe, result: ESBMCDirectResult, reading: EsbmcReading) -> dict[str, str]` com chaves `outcome` e `detail`; `run_probe(probe: Probe, esbmc_command: list[str], *, work_dir: Path, runner: Runner | None = None, bound: int = 5, timeout_seconds: int = 60) -> dict[str, str]`; `active_rules(outcomes: dict[str, str], probes: tuple[Probe, ...] = PROBES) -> frozenset[str]`.

- [ ] **Passo 1: testes que falham**

Trocar o bloco de imports de `tests/test_verify_capabilities.py` (as três linhas criadas na Tarefa 4) por:

```python
from pathlib import Path

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.capabilities import (
    ACEITA,
    INDETERMINADA,
    PROBES,
    RECUSA,
    Probe,
    active_rules,
    catalog_digest,
    named_exceptions,
    run_probe,
)
from research_pipeline.verify.rules import ALL_RULES, BUILTIN_NAMED_METHODS, NONE_ATTRIBUTE
```

(e apagar a linha antiga `from research_pipeline.verify.rules import ALL_RULES`). Acrescentar ao fim:

```python
BY_NAME = {p.name: p for p in PROBES}
NULL = "dereference failure: NULL pointer"


def _fixed_runner(status, properties=(), error=None):
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        calls.append(Path(path).stem)
        if error is not None:
            raise error
        return ESBMCDirectResult(source_file=str(path), status=status, command=list(esbmc_command), returncode=1,
                                 summary=status, details={"violated_properties": list(properties),
                                                          "violated_files": [Path(path).name] * len(properties)})
    run.calls = calls
    return run


def test_only_exceptions_esbmc_names_count():
    assert named_exceptions(["uncaught exception: AttributeError"]) == {"AttributeError"}
    assert named_exceptions(["TypeError: unsupported operand"]) == {"TypeError"}
    assert named_exceptions(["assertion s != 'ab 7'"]) == {"AssertionError"}
    assert named_exceptions(["division by zero"]) == {"ZeroDivisionError"}
    assert named_exceptions([NULL, "array bounds violated", "unwinding assertion loop 1"]) == frozenset()


@pytest.mark.parametrize(("name", "status", "properties", "expected"), [
    ("none_atributo_local", "violation_found", ["uncaught exception: AttributeError"], ACEITA),
    ("none_atributo_local", "violation_found", [NULL], RECUSA),
    ("none_atributo_local", "violation_found", ["uncaught exception: TypeError"], RECUSA),
    ("none_atributo_local", "no_violation_found", [], RECUSA),
    ("none_atributo_local", "tool_error", [], RECUSA),
    ("none_atributo_local", "timeout", [], INDETERMINADA),
    ("none_atributo_local", "skipped", [], INDETERMINADA),
    ("percent_valor", "no_violation_found", [], ACEITA),
    ("percent_valor", "violation_found", ["assertion s == 'ab 7'"], RECUSA),
])
def test_probe_outcome(tmp_path, name, status, properties, expected):
    outcome = run_probe(BY_NAME[name], ["esbmc"], work_dir=tmp_path, runner=_fixed_runner(status, properties))
    assert outcome["outcome"] == expected


def test_a_broken_runner_gives_an_indeterminate_probe(tmp_path):
    runner = _fixed_runner("violation_found", error=RuntimeError("boom"))
    outcome = run_probe(BY_NAME["metodo_get"], ["esbmc"], work_dir=tmp_path, runner=runner)
    assert outcome == {"outcome": INDETERMINADA, "detail": "RuntimeError: boom"}


def test_a_rule_goes_off_only_when_all_its_probes_are_accepted():
    outcomes = {p.name: ACEITA for p in PROBES}
    assert active_rules(outcomes) == frozenset()
    outcomes["none_atributo_campo"] = RECUSA
    assert active_rules(outcomes) == {NONE_ATTRIBUTE}
    del outcomes["metodo_get"]
    assert active_rules(outcomes) == {NONE_ATTRIBUTE, BUILTIN_NAMED_METHODS}
    assert active_rules({}) == ALL_RULES
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_capabilities.py -q`
Expected: FAIL na coleta com `ImportError: cannot import name 'active_rules' from 'research_pipeline.verify.capabilities'`.

- [ ] **Passo 3: implementação mínima**

Em `src/research_pipeline/verify/capabilities.py`, trocar o bloco de imports por:

```python
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from research_pipeline.models import ESBMCDirectResult

from .esbmc_run import Runner, check
from .outcome import EsbmcReading
from .rules import (
    ALL_RULES,
    BUILTIN_NAMED_METHODS,
    CONDITIONAL_ASSIGNMENTS,
    METHOD_ALIAS,
    NONE_ARITHMETIC,
    NONE_ATTRIBUTE,
    NONE_CALL,
    NONE_MEMBERSHIP,
    NONE_ORDERING,
    NONE_SUBSCRIPT,
    PERCENT_FORMAT,
    PROJECT_DECORATORS,
    PROPERTIES_AS_ATTRIBUTES,
)
```

Acrescentar ao fim do arquivo:

```python
_UNCAUGHT = re.compile(r"uncaught exception: ([A-Za-z_]\w*)")
_LEADING = re.compile(r"([A-Z]\w*(?:Error|Exception))\b")


def named_exceptions(properties: list[object]) -> frozenset[str]:
    """Exceptions ESBMC names itself. Memory-model messages do not count: without --no-pointer-check a
    None dereference reads as "NULL pointer", which outcome.py maps to AttributeError for the verdict."""
    names: set[str] = set()
    for text in map(str, properties):
        match = _UNCAUGHT.search(text) or _LEADING.match(text)
        if match:
            names.add(match.group(1))
        lowered = text.lower()
        if lowered.startswith("assertion "):
            names.add("AssertionError")
        if "division by zero" in lowered:
            names.add("ZeroDivisionError")
    return frozenset(names)


def classify_probe(probe: Probe, result: ESBMCDirectResult, reading: EsbmcReading) -> dict[str, str]:
    detail = f"{reading.kind}: {reading.message}"[:300]
    if reading.kind in {"timeout", "error"}:
        return {"outcome": INDETERMINADA, "detail": detail}
    if probe.exception is None:
        accepted = reading.kind == "safe"
    else:
        accepted = reading.kind == "violation" and probe.exception in named_exceptions(
            list(result.details.get("violated_properties") or []))
    return {"outcome": ACEITA if accepted else RECUSA, "detail": detail}


def run_probe(probe: Probe, esbmc_command: list[str], *, work_dir: Path, runner: Runner | None = None,
              bound: int = 5, timeout_seconds: int = 60) -> dict[str, str]:
    """The probe through the engine's own check(): same bounds, retries and solver fallbacks."""
    try:
        path = Path(work_dir) / f"{probe.name}.py"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(probe.source(), encoding="utf-8")
        result, reading, _ = check(path, esbmc_command=esbmc_command, bound=bound, timeout_seconds=timeout_seconds,
                                   work_dir=Path(work_dir) / probe.name, runner=runner)
    except Exception as exc:  # noqa: BLE001 - a broken probe keeps its rule on and never ends the batch
        return {"outcome": INDETERMINADA, "detail": f"{type(exc).__name__}: {exc}"[:300]}
    return classify_probe(probe, result, reading)


def active_rules(outcomes: dict[str, str], probes: tuple[Probe, ...] = PROBES) -> frozenset[str]:
    """Rules still needed: a rule goes off only when it has probes and every one of them is aceita."""
    off = {rule for rule in ALL_RULES
           if any(p.rule == rule for p in probes)
           and all(outcomes.get(p.name) == ACEITA for p in probes if p.rule == rule)}
    return ALL_RULES - off
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_capabilities.py -q`
Expected: PASS.

- [ ] **Passo 5: ponto de parada (sem commit)**

---

### Tarefa 6: identidade do ESBMC, cache e `resolve_rules`

**Files:**
- Modify: `src/research_pipeline/verify/capabilities.py`
- Test: `tests/test_verify_capabilities.py`

**Interfaces:**
- Consumes: `run_probe`, `active_rules`, `catalog_digest`, `PROBES` (Tarefas 4 e 5).
- Produces: `esbmc_identity(esbmc_command: list[str], timeout_seconds: int = 30) -> dict` (`command`, `version`, `files`); `cache_key(identity: dict, digest: str | None = None) -> str`; `all_rules_report(reason: str) -> dict`; `probe_capabilities(esbmc_command: list[str], *, cache_dir: Path, runner: Runner | None = None, identity: dict | None = None, bound: int = 5, timeout_seconds: int = 60) -> dict`; `resolve_rules(esbmc_command: list[str] | None, *, cache_dir: Path, enabled: bool = True, resumed: bool = False, runner: Runner | None = None, identity: dict | None = None) -> dict`. Relatório: `{"reason": str, "key": str, "identity": dict, "active_rules": list[str], "disabled_rules": list[str], "results": {probe: {"outcome": str, "detail": str}}}`.

- [ ] **Passo 1: testes que falham**

No bloco de imports de `tests/test_verify_capabilities.py`, trocar `from research_pipeline.verify.capabilities import (` e a lista por:

```python
from research_pipeline.verify import capabilities
from research_pipeline.verify.capabilities import (
    ACEITA,
    INDETERMINADA,
    PROBES,
    RECUSA,
    Probe,
    active_rules,
    cache_key,
    catalog_digest,
    esbmc_identity,
    named_exceptions,
    probe_capabilities,
    resolve_rules,
    run_probe,
)
```

Acrescentar ao fim:

```python
IDENTITY = {"command": ["esbmc"], "version": "ESBMC version 8.5.0", "files": {"/x/esbmc": "abc"}}


def _probe_runner(refuse=(), timeout=()):
    """Answers each probe as a correct ESBMC would, except the names in ``refuse`` and ``timeout``."""
    calls = []

    def run(path, *, esbmc_command, bound, timeout_seconds, output_dir, bound_flags, extra_flags):
        name = Path(path).stem
        calls.append(name)
        probe = BY_NAME[name]
        if name in timeout:
            status, properties = "timeout", []
        elif (probe.exception is None) != (name in refuse):
            status, properties = "no_violation_found", []
        else:
            status, properties = "violation_found", [f"uncaught exception: {probe.exception or 'AssertionError'}"]
        return ESBMCDirectResult(source_file=str(path), status=status, command=list(esbmc_command), returncode=1,
                                 summary=status, details={"violated_properties": properties,
                                                          "violated_files": [Path(path).name] * len(properties)})
    run.calls = calls
    return run


def test_accepted_probes_switch_every_rule_off_and_the_cache_spares_the_next_batch(tmp_path):
    runner = _probe_runner()
    first = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=runner, identity=IDENTITY)
    assert first["active_rules"] == [] and first["disabled_rules"] == sorted(ALL_RULES)
    assert sorted(runner.calls) == sorted(BY_NAME)
    again = _probe_runner()
    second = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=again, identity=IDENTITY)
    assert again.calls == [] and second["active_rules"] == []


def test_one_refused_probe_keeps_only_its_rule_on(tmp_path):
    report = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=_probe_runner(refuse={"none_atributo_campo"}),
                                identity=IDENTITY)
    assert report["active_rules"] == [NONE_ATTRIBUTE]
    assert report["results"]["none_atributo_campo"]["outcome"] == RECUSA


def test_an_indeterminate_probe_keeps_its_rule_on_and_runs_again_next_batch(tmp_path):
    report = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=_probe_runner(timeout={"metodo_get"}),
                                identity=IDENTITY)
    assert report["active_rules"] == [BUILTIN_NAMED_METHODS]
    assert report["results"]["metodo_get"]["outcome"] == INDETERMINADA
    again = _probe_runner()
    second = probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=again, identity=IDENTITY)
    assert set(again.calls) == {"metodo_get"} and second["active_rules"] == []


def test_a_corrupt_cache_is_ignored(tmp_path):
    (tmp_path / f"{cache_key(IDENTITY)}.json").write_text("{not json", encoding="utf-8")
    runner = _probe_runner()
    assert probe_capabilities(["esbmc"], cache_dir=tmp_path, runner=runner, identity=IDENTITY)["active_rules"] == []
    assert len(runner.calls) == len(PROBES)


def test_cache_key_changes_with_binary_flags_and_catalog():
    keys = {
        cache_key(IDENTITY),
        cache_key({**IDENTITY, "files": {"/x/esbmc": "abd"}}),
        cache_key({**IDENTITY, "command": ["esbmc", "--no-pointer-check"]}),
        cache_key({**IDENTITY, "version": "ESBMC version 8.6.0"}),
        cache_key(IDENTITY, "outro catálogo"),
    }
    assert len(keys) == 5


def test_identity_follows_the_binary_a_wrapper_names(tmp_path):
    binary = tmp_path / "esbmc-real"
    binary.write_bytes(b"v1")
    wrapper = tmp_path / "esbmc.sh"
    wrapper.write_text(f'#!/bin/sh\nexec {binary} --no-pointer-check "$@"\n', encoding="utf-8")
    wrapper.chmod(0o755)
    before = esbmc_identity([str(wrapper)])
    assert str(binary.resolve()) in before["files"]
    binary.write_bytes(b"v2")
    assert cache_key(esbmc_identity([str(wrapper)])) != cache_key(before)


@pytest.mark.parametrize(("kwargs", "reason"), [
    ({"enabled": False}, "sondas desligadas"),
    ({"resumed": True}, "retomada"),
])
def test_resolve_rules_keeps_every_rule_without_probing(tmp_path, kwargs, reason):
    runner = _probe_runner()
    report = resolve_rules(["esbmc"], cache_dir=tmp_path, runner=runner, identity=IDENTITY, **kwargs)
    assert report["active_rules"] == sorted(ALL_RULES) and reason in report["reason"] and runner.calls == []


def test_resolve_rules_without_esbmc_or_on_a_failure_keeps_every_rule(tmp_path, monkeypatch):
    assert resolve_rules(None, cache_dir=tmp_path)["active_rules"] == sorted(ALL_RULES)

    def broken(esbmc_command, timeout_seconds=30):
        raise OSError("disk")

    monkeypatch.setattr(capabilities, "esbmc_identity", broken)
    report = resolve_rules(["esbmc"], cache_dir=tmp_path)
    assert report["active_rules"] == sorted(ALL_RULES) and "OSError" in report["reason"]
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_capabilities.py -q`
Expected: FAIL na coleta com `ImportError: cannot import name 'cache_key' from 'research_pipeline.verify.capabilities'`.

- [ ] **Passo 3: implementação mínima**

Em `src/research_pipeline/verify/capabilities.py`, trocar as linhas de import da biblioteca padrão (de `import hashlib` até `from pathlib import Path`) por:

```python
import hashlib
import json
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
```

Acrescentar ao fim do arquivo:

```python
_SCRIPT_LIMIT = 64 * 1024
_ABSOLUTE_PATH = re.compile(r"(/[\w.@+-]+(?:/[\w.@+-]+)+)")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def esbmc_identity(esbmc_command: list[str], timeout_seconds: int = 30) -> dict:
    """What decides ESBMC's answers: the command with its flags, ``--version``, and the hash of the
    executable; for a wrapper script, also of every existing file it names (the real binary)."""
    files: dict[str, str] = {}
    executable = shutil.which(esbmc_command[0])
    if executable:
        path = Path(executable).resolve()
        files[str(path)] = _sha256(path)
        head = path.read_bytes() if path.stat().st_size <= _SCRIPT_LIMIT else b""
        if head.startswith(b"#!"):
            for named in _ABSOLUTE_PATH.findall(head.decode("utf-8", errors="replace")):
                target = Path(named)
                if target.is_file():
                    files[str(target.resolve())] = _sha256(target)
    try:
        done = subprocess.run([*esbmc_command, "--version"], capture_output=True, text=True,
                              timeout=timeout_seconds, check=False)
        version = (done.stdout or done.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        version = f"unavailable: {type(exc).__name__}"
    return {"command": list(esbmc_command), "version": version, "files": files}


def cache_key(identity: dict, digest: str | None = None) -> str:
    payload = json.dumps({"identity": identity, "probes": digest or catalog_digest()}, sort_keys=True)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


def _load_cache(path: Path) -> dict[str, dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, dict):
        return {}
    known = {p.name for p in PROBES}
    return {name: entry for name, entry in results.items()
            if name in known and isinstance(entry, dict) and entry.get("outcome") in {ACEITA, RECUSA}}


def _store_cache(path: Path, key: str, identity: dict, results: dict[str, dict[str, str]]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        partial = path.with_suffix(".tmp")
        partial.write_text(json.dumps({"key": key, "identity": identity,
                                       "created_at": datetime.now(timezone.utc).isoformat(),
                                       "results": results}, indent=2, sort_keys=True), encoding="utf-8")
        partial.replace(path)
    except OSError:
        pass  # without a cache the next batch probes again; this batch keeps what it measured


def _report(reason: str, active: frozenset[str], key: str = "", identity: dict | None = None,
            results: dict[str, dict[str, str]] | None = None) -> dict:
    return {"reason": reason, "key": key, "identity": identity or {}, "active_rules": sorted(active),
            "disabled_rules": sorted(ALL_RULES - active), "results": results or {}}


def all_rules_report(reason: str) -> dict:
    return _report(reason, ALL_RULES)


def probe_capabilities(esbmc_command: list[str], *, cache_dir: Path, runner: Runner | None = None,
                       identity: dict | None = None, bound: int = 5, timeout_seconds: int = 60) -> dict:
    """Runs the probes the cache lacks; only aceita and recusa are cached, so an indeterminate probe
    (timeout, crash) is tried again by the next batch."""
    identity = esbmc_identity(esbmc_command) if identity is None else identity
    key = cache_key(identity)
    path = Path(cache_dir) / f"{key}.json"
    cached = _load_cache(path)
    results = dict(cached)
    pending = [p for p in PROBES if p.name not in results]
    if pending:
        with tempfile.TemporaryDirectory(prefix="esbmc_probes_") as tmp:
            for probe in pending:
                results[probe.name] = run_probe(probe, esbmc_command, work_dir=Path(tmp), runner=runner,
                                                bound=bound, timeout_seconds=timeout_seconds)
    determinate = {name: entry for name, entry in results.items() if entry["outcome"] != INDETERMINADA}
    if determinate != cached:
        _store_cache(path, key, identity, determinate)
    active = active_rules({name: entry["outcome"] for name, entry in results.items()})
    return _report("sondas", active, key, identity, results)


def resolve_rules(esbmc_command: list[str] | None, *, cache_dir: Path, enabled: bool = True,
                  resumed: bool = False, runner: Runner | None = None, identity: dict | None = None) -> dict:
    """The rule set for one batch. Every rule stays on with the probes switched off, on a resume of a
    batch begun before the probes existed, without an ESBMC command, or on any failure of the probes."""
    if not enabled:
        return all_rules_report("sondas desligadas (--no-capability-probes)")
    if resumed:
        return all_rules_report("retomada de lote iniciado sem sondas")
    if not esbmc_command:
        return all_rules_report("sem comando ESBMC")
    try:
        return probe_capabilities(esbmc_command, cache_dir=cache_dir, runner=runner, identity=identity)
    except Exception as exc:  # noqa: BLE001 - the probes may switch rules off, never stop a batch
        return all_rules_report(f"falha nas sondas: {type(exc).__name__}: {exc}")
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_capabilities.py -q`
Expected: PASS.

- [ ] **Passo 5: ponto de parada (sem commit)**

---

### Tarefa 7: ligar no modo v2, opções de linha de comando e teste de integração

**Files:**
- Modify: `src/main.py`
- Create: `tests/conftest.py`
- Modify: `tests/test_main_v2.py`, `tests/test_verify_esbmc_integration.py`
- Modify: `docs/projeto/PLANO_GERAL_2026-10-15.md` (estado do item 2)

**Interfaces:**
- Consumes: `resolve_rules(...) -> dict`, `all_rules_report(reason) -> dict`, `probe_capabilities(...)` (Tarefa 6); `run_verify(..., **kwargs)` repassa `rules` a `verify_hypothesis` (Tarefa 3); `_save_checkpoint(path, payload)` em `main.py`.
- Produces: opções `--no-capability-probes` (`args.capability_probes: bool`, padrão `True`) e `--capability-cache DIR` (padrão `artifacts/esbmc_capabilities`); `checkpoint["capabilities"]` e `config.capabilities` no `v2_verify_report.json`; `main.resolve_rules` importado no módulo (alvo da fixture).

- [ ] **Passo 1: testes que falham**

Criar `tests/conftest.py`:

```python
"""Tests never run the real ESBMC capability probes through main; test_verify_capabilities.py
calls them directly with a fake runner."""

import sys

import pytest


@pytest.fixture(autouse=True)
def _capability_probes_off(monkeypatch):
    module = sys.modules.get("main")
    if module is not None and hasattr(module, "resolve_rules"):
        from research_pipeline.verify.capabilities import all_rules_report

        monkeypatch.setattr(module, "resolve_rules", lambda *args, **kwargs: all_rules_report("testes"))
```

Acrescentar ao fim de `tests/test_main_v2.py`:

```python
def test_v2_verify_gets_the_probed_rules_and_a_resume_reuses_them(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    report = {"reason": "sondas", "key": "k", "identity": {}, "active_rules": ["none_guards_attribute"],
              "disabled_rules": ["compat_percent_format"], "results": {}}
    calls, seen = [], {}

    def fake_resolve(esbmc_command, **kwargs):
        calls.append(kwargs)
        return report

    def fake_verify(hypotheses, **kwargs):
        seen["rules"] = kwargs["rules"]
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "resolve_rules", fake_resolve)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    out = tmp_path / "out"
    base = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(out)]

    assert main.mode_v2(main.build_parser().parse_args(base)) == 0
    assert seen["rules"] == frozenset({"none_guards_attribute"})
    assert calls[0]["enabled"] is True and calls[0]["resumed"] is False
    assert json.loads((out / "v2_verify_report.json").read_text())["config"]["capabilities"] == report
    assert json.loads((out / "v2_checkpoint.json").read_text())["capabilities"] == report
    assert main.mode_v2(main.build_parser().parse_args([*base, "--resume"])) == 0
    assert len(calls) == 1 and seen["rules"] == frozenset({"none_guards_attribute"})


def test_no_capability_probes_flag_reaches_resolve_rules() -> None:
    args = main.build_parser().parse_args(["--mode", "hybrid", "--input", "x.py", "--no-capability-probes",
                                           "--capability-cache", "cache"])
    assert args.capability_probes is False and args.capability_cache == "cache"
    assert main.build_parser().parse_args(["--mode", "hybrid", "--input", "x.py"]).capability_probes is True
```

Acrescentar ao fim de `tests/test_verify_esbmc_integration.py`:

```python
WRAPPER = Path(__file__).resolve().parents[1] / "artifacts/v2/final-2026-10-15/esbmc.sh"
MASTER = Path("/home/fernanda/esbmc-master/build/src/esbmc/esbmc")


@pytest.mark.skipif(not (WRAPPER.exists() and MASTER.exists()), reason="ESBMC master wrapper not available")
def test_probes_on_master_keep_the_rules_its_known_gaps_need(tmp_path):
    from research_pipeline.verify.capabilities import ACEITA, probe_capabilities
    from research_pipeline.verify.rules import BUILTIN_NAMED_METHODS, NONE_ATTRIBUTE

    report = probe_capabilities([str(WRAPPER)], cache_dir=tmp_path)
    # possiveis_problemas 25 and 27: SUCCESSFUL on master 333d07cc8a with the wrapper's flags.
    assert report["results"]["none_atributo_campo"]["outcome"] != ACEITA
    assert report["results"]["metodo_append"]["outcome"] != ACEITA
    assert {NONE_ATTRIBUTE, BUILTIN_NAMED_METHODS} <= set(report["active_rules"])
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_main_v2.py -q`
Expected: FAIL: `AttributeError: <module 'main'> has no attribute 'resolve_rules'` no teste novo (o `monkeypatch.setattr` exige o atributo) e `SystemExit: 2` (opção desconhecida `--no-capability-probes`) no teste da opção.

- [ ] **Passo 3: implementação mínima**

Em `src/main.py`, junto dos outros imports de `research_pipeline.verify`, acrescentar:

```python
from research_pipeline.verify.capabilities import resolve_rules
```

Logo depois do `parser.add_argument("--spec-strategy", ...)`, acrescentar:

```python
    parser.add_argument(
        "--no-capability-probes",
        dest="capability_probes",
        action="store_false",
        help="Motor verify: não roda as sondas de capacidade do ESBMC; todas as regras de reescrita "
             "ficam ligadas (para reproduzir uma rodada congelada).",
    )
    parser.add_argument(
        "--capability-cache",
        default="artifacts/esbmc_capabilities",
        metavar="DIR",
        help="Motor verify: cache das sondas, uma entrada por binário, flags e versão do ESBMC.",
    )
```

Em `_mode_v2_verify`, logo antes de `try:` que envolve `results = run_verify(`, acrescentar:

```python
    capabilities = checkpoint.get("capabilities")
    if capabilities is None:
        # A batch keeps one rule set: a resume reuses it, and a batch begun before the probes keeps them all.
        capabilities = resolve_rules(args.esbmc_command, cache_dir=Path(args.capability_cache),
                                     enabled=args.capability_probes,
                                     resumed=bool(checkpoint.get("verify_results")))
        checkpoint["capabilities"] = capabilities
        _save_checkpoint(checkpoint_path, checkpoint)
    if capabilities["disabled_rules"]:
        print("Regras desligadas pelas sondas: " + ", ".join(capabilities["disabled_rules"]))
```

Na chamada `run_verify(`, acrescentar depois de `strict_sources=args.verification_sources_strict,`:

```python
            rules=frozenset(capabilities["active_rules"]),
```

No relatório, trocar a linha

```python
        "config": {**config, "esbmc_version": _esbmc_version(args.esbmc_command or ["esbmc"])},
```

por

```python
        "config": {**config, "esbmc_version": _esbmc_version(args.esbmc_command or ["esbmc"]),
                   "capabilities": capabilities},
```

Conferir que todo `run_verify` falso em `tests/test_main_v2.py` aceita `**kwargs` (hoje todos aceitam: linhas 75, 99, 126, 152, 196, 269).

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_main_v2.py tests/test_verify_capabilities.py tests/test_scan_pipeline.py tests/test_verify_cli.py -q`
Expected: PASS.

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: 0 failed.

Opcional, só com o ESBMC master compilado e com o aval da Fernanda (roda o ESBMC real, alguns minutos na primeira vez):
Run: `.venv/bin/python -m pytest tests/test_verify_esbmc_integration.py -q -k probes_on_master`
Expected: PASS, ou SKIPPED se o wrapper ou o binário não existirem.

- [ ] **Passo 5: atualizar o estado do item 2**

Em `docs/projeto/PLANO_GERAL_2026-10-15.md`, na tabela de estado, trocar a célula do item 2 de `a fazer` para `implementado, falta rodar as sondas no primeiro lote do item 6`.

- [ ] **Passo 6: ponto de parada (sem commit)**
