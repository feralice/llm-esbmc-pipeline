# Funções aninhadas: entrada pela função de fora e levantamento — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** bugs em funções internas passam a ser verificáveis: o motor entra pela função de fora quando ela chama a interna (a), levanta a interna quando não chama (b), e a validação, o scan e o braço de agente enxergam a interna.

**Architecture:** um localizador por caminho (`find_definition`) e um detector de entrada pela de fora (`outer_entry`) em `verify/astutil.py`; `ground` tenta (a) antes do levantamento atual; a validação e o `agent_arm` passam a localizar com `locate`; o grafo do scan marca internas não async como verificáveis.

**Tech Stack:** Python 3.12, `ast`, pytest.

**Spec:** `docs/superpowers/specs/2026-11-02-funcoes-aninhadas-design.md`

## Global Constraints

- `find_function` não muda de comportamento (o `ground` depende do `None` dele para tentar o levantamento).
- Corpo da interna nunca é alterado; o caminho de entrada fica em `transforms`: `nested_entry_via_outer:<nome original>` ou `nested_entry_hoisted:<nome>` (este já existe).
- Interna com `nonlocal` e classe interna com captura continuam recusadas no levantamento.
- Branch `feat/harness-de-agente`, sem branch nova; commits sem coautoria do Claude.
- Testes novos mostrados falhando antes da mudança; suíte inteira passando no fim (`python -m pytest -q`, até 10 min).

## Review Focus

- Programa levantado contém duas definições com o mesmo nome (a interna original e a cópia): `locate` precisa achar a cópia do módulo, não a interna. Teste na Task 3.
- Função de fora async chamando a interna: (a) não pode entrar por ela; cai no levantamento. Teste na Task 2.
- Interna definida duas vezes em ramos diferentes (`if`/`else`): `outer_entry` usa a que contém a expressão, como `_nested_chain` já faz. Teste na Task 1.
- Interna só referenciada (devolvida, passada como callback), sem chamada: segue no levantamento. Teste na Task 2.
- Nome repetido entre uma interna e uma função do módulo: `locate` prefere a do módulo só quando o caminho pedido é o do módulo. Coberto pelo teste de programa levantado da Task 3.

---

### Task 1: localizar por caminho e detectar a entrada pela de fora

**Files:**
- Modify: `src/research_pipeline/verify/astutil.py`
- Modify: `src/research_pipeline/verify/grounding.py:406-441` (mover `_definitions_in` e `_nested_chain` para `astutil`, importar de lá)
- Test: `tests/test_verify_nested.py` (novo)

**Interfaces:**
- Produces: `definitions_in(body: list[ast.stmt], name: str) -> list[ast.AST]`; `nested_chain(tree: ast.Module, qualified: str, expression: str = "") -> list[ast.AST] | None` (mesmo comportamento das privadas de hoje); `find_definition(tree: ast.Module, qualified: str, expression: str = "") -> ast.FunctionDef | None` (resolve qualquer profundidade, atravessando classes e funções, inclusive sob if/try/with/for; `None` se ambígua ou async); `outer_entry(tree: ast.Module, qualified: str, expression: str = "") -> str | None` (nome qualificado da função de fora mais externa que `find_function` localiza, quando cada elo da cadeia chama o próximo; `None` caso contrário).

- [ ] **Step 1: testes que falham**

```python
def test_find_definition_resolves_any_depth():
    assert find_definition(ast.parse(FOUR_LEVELS), "A.f.g.h.i").name == "i"
    assert find_definition(ast.parse(FOUR_LEVELS), "A.f.g.x") is None

def test_outer_entry_when_every_link_calls_the_next():
    assert outer_entry(ast.parse(FOUR_LEVELS), "A.f.g.h.i") == "A.f"
    assert outer_entry(ast.parse(NONLOCAL), "f.add") == "f"
    assert outer_entry(ast.parse(INNER_CLASS), "f.C.m") == "f"      # f faz C().m()

def test_no_outer_entry_for_a_callback_or_a_returned_closure():
    assert outer_entry(ast.parse(CALLBACK), "f.cb") is None          # request.errback = cb
    assert outer_entry(ast.parse(RETURNED), "outer.inner") is None   # return inner

def test_outer_entry_picks_the_branch_holding_the_expression():
    assert outer_entry(ast.parse(TWO_BRANCHES), "f.g", "10 // k") == "f"
```

`FOUR_LEVELS`, `NONLOCAL` e `INNER_CLASS` são os programas da sonda de 02/11 (spec); `CALLBACK` atribui a interna a um atributo; `RETURNED` devolve a interna; `TWO_BRANCHES` define `g` em `if`/`else`, só uma com `10 // k`, e chama `g` depois.

- [ ] **Step 2:** `python -m pytest tests/test_verify_nested.py -q` → FAIL (ImportError).
- [ ] **Step 3:** implementar. "Chama o próximo" = no corpo do elo, fora de definições internas a ele, existe `ast.Call` cujo `func` é `Name(next)`; elo classe: existe chamada `Attribute(attr=metodo)` e a classe é chamada (`Name(classe)`) no mesmo corpo. A função de fora é o primeiro elo da cadeia (prefixo de 1 ou 2 partes) que `find_function` localiza e que não é async.
- [ ] **Step 4:** `python -m pytest tests/test_verify_nested.py tests/test_verify_review_fixes.py -q` → PASS.
- [ ] **Step 5:** commit `Locate nested definitions by path and detect an entry through the enclosing function`.

### Task 2: (a) no motor, antes do levantamento

**Files:**
- Modify: `src/research_pipeline/verify/grounding.py` (`ground`, ramo `function is None`)
- Test: `tests/test_verify_nested.py`

**Interfaces:**
- Consumes: `outer_entry` (Task 1).
- Produces: `Grounded.transforms[0] == f"nested_entry_via_outer:{h.function}"` quando entra pela de fora; `grounded.hypothesis.function` é o nome da de fora e a linha não muda.

- [ ] **Step 1: testes que falham**

```python
def test_nonlocal_and_inner_class_ground_through_the_outer_function():
    for src, name, expr in [(NONLOCAL, "f.add", "10 // x"), (INNER_CLASS, "f.C.m", "10 // k")]:
        g = ground(BugHypothesis("x.py", name, expr, line=5), src)
        assert isinstance(g, Grounded) and g.transforms[0] == f"nested_entry_via_outer:{name}"
        assert g.hypothesis.function == "f"

def test_four_levels_enter_through_the_method():
    g = ground(BugHypothesis("x.py", "A.f.g.h.i", "10 // (z - n + k)", line=6), FOUR_LEVELS)
    assert g.transforms[0] == "nested_entry_via_outer:A.f.g.h.i" and g.hypothesis.function == "A.f"

def test_callback_and_async_outer_still_hoist():
    assert ground(BugHypothesis("x.py", "f.cb", "10 // x", line=3), CALLBACK).transforms[0].startswith("nested_entry_hoisted:")
    assert ground(BugHypothesis("x.py", "f.g", "10 // k", line=3), ASYNC_OUTER).transforms[0].startswith("nested_entry_hoisted:")
```

`ASYNC_OUTER`: `async def f` que chama `g` (síncrona) interna. Se o ramo de async atual do `ground` recusar esse caso antes, o teste fixa a ordem: (a) → levantamento → recusa de async só quando a própria alvo é async.

- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** no ramo `function is None`, antes de `_hoist_nested`: `outer = outer_entry(tree, h.function, h.suspect_expression)`; se houver, `ground(replace(h, function=outer), source, ...)`; se `Grounded`, prefixar o transform; senão seguir para o levantamento.
- [ ] **Step 4:** `python -m pytest tests/test_verify_nested.py tests/test_verify_review_fixes.py -q` → PASS (o teste existente de levantamento usa closure devolvida, segue levantado).
- [ ] **Step 5:** commit `Ground a nested function through the enclosing function that calls it`.

### Task 3: validação e agente localizam a interna

**Files:**
- Modify: `src/research_pipeline/verify/astutil.py` (`locate`)
- Modify: `src/research_pipeline/verify/validation.py:22-56` (`program_for_result`, `target_preserved`)
- Modify: `src/research_pipeline/verify/agent_arm.py:219-225` (`_target` vira `locate`) e `_PROMPT` (linha nova)
- Test: `tests/test_verify_nested.py`

**Interfaces:**
- Consumes: `find_definition` (Task 1).
- Produces: `locate(tree: ast.Module, qualified: str) -> ast.FunctionDef | None`: `find_function` → `find_definition` → única `FunctionDef` com o último nome em todo o arquivo. `nested_hint(source: str, function: str) -> str` em `agent_arm.py`: `""` quando `find_function` acha; senão a linha do prompt.

- [ ] **Step 1: testes que falham**

```python
def test_target_preserved_sees_an_untouched_nested_function():
    assert target_preserved(FOUR_LEVELS, FOUR_LEVELS, "A.f.g.h.i")
    assert not target_preserved(FOUR_LEVELS, FOUR_LEVELS.replace("10 //", "11 //"), "A.f.g.h.i")

def test_target_preserved_matches_the_hoisted_copy():
    g = ground(BugHypothesis("x.py", "f.cb", "10 // x", line=3), CALLBACK)
    program = render_program(g, InputSpec({p.name: "int" for p in g.params}, {}, ()))
    assert target_preserved(CALLBACK, program.source, g.hypothesis.function)

def test_agent_prompt_says_where_a_nested_target_lives():
    assert "defined inside `f`" in nested_hint(CALLBACK, "f.cb")
    assert nested_hint(CALLBACK, "f") == ""
```

Texto da linha (copiar): ``"`{function}` is defined inside `{outer}`: call `{outer}` so it runs `{name}`, or copy `{name}` to module level with the names it takes from `{outer}` as keyword-only parameters. Never change its body.\n"``

- [ ] **Step 2:** rodar → FAIL.
- [ ] **Step 3:** implementar; `target_preserved` e `program_for_result` usam `locate` nos dois lados; `_PROMPT` ganha `{nested}` depois da linha de `Goal`.
- [ ] **Step 4:** `python -m pytest tests/test_verify_nested.py tests/test_verify_validation*.py tests/test_verify_agent*.py -q` → PASS.
- [ ] **Step 5:** commit `Let validation and the agent arm find nested targets`.

### Task 4: scan seleciona internas

**Files:**
- Modify: `src/research_pipeline/scan/callgraph.py:46-48` (`verifiable`)
- Modify: `src/research_pipeline/scan/pipeline.py:131,186-192` (contagem e resumo)
- Test: `tests/test_scan_*.py` existente do callgraph (acrescentar)

**Interfaces:**
- Produces: `FunctionNode.verifiable` verdadeiro para interna não async e não ambígua; `select_targets(..., excluded=counts)` passa a preencher `counts["nested"]` com quantas internas entraram na seleção; o resumo impresso acrescenta `"{n} interna(s) incluída(s)"`.

- [ ] **Step 1: teste que falha**

```python
def test_nested_sync_functions_are_selectable_and_async_ones_are_not(tmp_path):
    (tmp_path / "m.py").write_text("def f(n):\n    def g(k):\n        return 10 // k\n    return g(n)\n"
                                   "async def a():\n    def b(x):\n        return 1 // x\n    return b(1)\n")
    graph = build_graph(tmp_path)
    assert graph.functions["m:f.g"].verifiable
    counts = {}
    keys = {t.key for t in select_targets(graph, excluded=counts)[0]}
    assert "m:f.g" in keys and "m:a.b" not in keys and counts["nested"] == 1
```

(`build_graph`: o construtor do grafo que os testes de scan já usam; conferir o nome no arquivo de teste.)

- [ ] **Step 2:** rodar → FAIL. **Step 3:** implementar (interna dentro de async conta como async: herdar `is_async` do elo de fora na seleção). **Step 4:** `python -m pytest tests/ -q -k scan` → PASS. **Step 5:** commit `Select nested functions in the scan`.

### Task 5: medição offline e registro

**Files:**
- Create: `scripts/nested_grounding_census.py`
- Modify: `docs/experimentos/README.md`, `docs/projeto/PLANO_2026-10-19.md` (item sai do Depois)

**Interfaces:**
- Consumes: `build_graph`, `ground`, `BugHypothesis`.
- Produces: `python scripts/nested_grounding_census.py <repo> [--json out]` imprime contagem `{"via_outer", "hoisted", "failed", "async"}` das internas do grafo, cada uma com hipótese sintética na primeira divisão ou subscrito do corpo (ou, sem ela, no primeiro `return`).

- [ ] **Step 1:** escrever o script logo depois da Task 1 (só depende de `ground` e do grafo) e rodar em `~/alvos/PyAthena-limpo` antes da Task 2 (linha de base); rodar de novo no fim; anotar os dois números.
- [ ] **Step 2:** seção nova no README (data, commit, comando, resultado, pergunta); riscar o item no Depois do plano.
- [ ] **Step 3:** suíte inteira `timeout 600 python -m pytest -q` → todos passando.
- [ ] **Step 4:** commit `Measure nested-function grounding on PyAthena and record it`.
