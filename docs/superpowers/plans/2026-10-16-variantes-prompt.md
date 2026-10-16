# Variantes de prompt A13 e A14: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** implementar duas variantes do prompt de detecção que se compõem com A5 (`A1,A2`): A13 (k bugs reais do gabarito como exemplos, escolhidos por similaridade, nunca do mesmo projeto) e A14 (linha citada e condição de disparo em cada achado), mais um script que imprime os prompts sem chamar LLM e o backend escolhível em `run_detection_variants.sh`, para o item 6 rodar com Gemini.

**Architecture:** um módulo novo, `llm/example_pool.py`, carrega o pool do gabarito e escolhe exemplos (puro, sem LLM). As variantes entram como as anteriores: texto do prompt de sistema em `prompt_variants.py`, campos do esquema em `schema.py`, bloco por função em `prompts.build_user_prompt` com estado global configurado por `set_example_pool` (mesmo padrão de `set_context_sources`). `main.py` ganha `--example-pool` e `--example-k` e amplia a impressão digital só quando A13 ou A14 são pedidos.

**Tech Stack:** Python 3 do `.venv`, `ast`, `hashlib`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-16-variantes-prompt-design.md`

## Global Constraints

- Nenhuma chamada a LLM, nenhuma rodada, nenhuma comparação: a medição é o item 6.
- Não editar `dataset/` nem `artifacts/`.
- A rodada pausada `artifacts/v2/final-2026-10-15-codex` (A1,A2) tem que continuar retomável: `config`, `detector_schema` e as chaves da impressão digital de A1,A2 não mudam.
- `system_prompt_v2.txt` não muda; as variantes só acrescentam texto por `_swap`.
- Sem travessão em texto; sem commit (cada passo "commit" vira "ponto de parada (sem commit)").
- Teste de um arquivo: `.venv/bin/python -m pytest tests/<arquivo> -q`.
- Suíte: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`.
- Depois da Tarefa 5, rodar `pylint` nos arquivos novos e tocados e corrigir o que for erro.

## Review Focus

- **Vazamento no few-shot:** o próprio bug ou outro bug do mesmo projeto aparece como exemplo (teste `test_never_selects_the_bug_itself_or_its_project`, Tarefa 2).
- **A13 sem pool vira zero-shot em silêncio:** pedir A13 sem `set_example_pool` tem que levantar erro (teste `test_a13_without_a_pool_fails_loudly`, Tarefa 3; `test_a13_with_a_missing_pool_exits_with_error`, Tarefa 3).
- **Retomada quebrada:** a impressão digital de A1,A2 ganha chave nova e a rodada pausada deixa de retomar (teste `test_fingerprint_keeps_its_keys_for_earlier_variants`, Tarefa 3).
- **Prompt e esquema divergentes:** A14 pede campo que o esquema estrito não declara (claude_cli/OpenAI recusam) ou o backend sem esquema (Gemini) perde os campos (testes `test_a14_asks_for_the_quoted_line_and_trigger_in_prompt_and_schema` e `test_a14_fields_survive_a_backend_without_schema`, Tarefa 1).
- **Exemplos não determinísticos:** empate de similaridade resolvido por ordem de conjunto muda os exemplos entre rodadas (teste `test_ties_break_by_id_so_runs_repeat`, Tarefa 2).
- **"Inspeção" que chama LLM:** o script de impressão não pode tocar rede nem subprocesso (fixture `no_llm`, Tarefa 4).

---

### Tarefa 1: variante A14 (evidência citada)

**Files:**
- Modify: `src/research_pipeline/llm/prompt_variants.py`
- Modify: `src/research_pipeline/llm/schema.py`
- Modify: `src/research_pipeline/llm/findings.py`
- Test: `tests/test_prompt_variants.py`

**Interfaces:**
- Produces: variante `"A14"` em `VARIANTS`; `v2_findings_schema(variants: tuple[str, ...] = ()) -> dict` passa a declarar `quoted_line` e `trigger` (string, obrigatórios) em `metadata` quando `"A14" in variants`; `finding_from_dict(data: dict) -> Finding` guarda `metadata["quoted_line"]` e `metadata["trigger"]` (`""` quando ausentes).

- [ ] **Passo 1: testes que falham** (acrescentar ao fim de `tests/test_prompt_variants.py`)

```python
def test_a14_asks_for_the_quoted_line_and_trigger_in_prompt_and_schema() -> None:
    changed = apply_variants(BASE, ("A14",))
    assert changed.index("## EVIDÊNCIA CITADA") < changed.index("## SAÍDA")
    assert '"quoted_line"' in changed and '"trigger"' in changed
    metadata = v2_findings_schema(("A14",))["schema"]["properties"]["findings"]["items"]["properties"]["metadata"]
    for field in ("quoted_line", "trigger"):
        assert field in metadata["properties"] and field in metadata["required"]


def test_a14_fields_survive_a_backend_without_schema() -> None:
    raw = {"metadata": {"expression": "xs[k]", "quoted_line": "return xs[k]", "trigger": "k >= len(xs)"},
           "verifiable": True}
    finding = finding_from_dict(raw)
    assert finding.metadata["quoted_line"] == "return xs[k]"
    assert finding.metadata["trigger"] == "k >= len(xs)"
    assert finding_from_dict({"metadata": {"expression": "xs[k]"}}).metadata["trigger"] == ""


def test_a14_and_a9_compose_in_the_schema() -> None:
    metadata = v2_findings_schema(("A9", "A14"))["schema"]["properties"]["findings"]["items"]["properties"]["metadata"]
    assert {"crash_expression", "quoted_line", "trigger"} <= set(metadata["required"])
    assert v2_findings_schema(("A9",)) != v2_findings_schema(("A9", "A14"))
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_prompt_variants.py -q`
Expected: 3 falhas: `ValueError: unknown V2 prompt variant 'A14'` no primeiro, `KeyError: 'quoted_line'` no segundo, `AssertionError` no terceiro; os 19 anteriores passam.

- [ ] **Passo 3: implementação**

Em `src/research_pipeline/llm/prompt_variants.py`, antes de `VARIANTS`:

```python
_QUOTED_EVIDENCE = """## EVIDÊNCIA CITADA

Para cada achado, preencha mais dois campos em `metadata`:
- `quoted_line`: a linha inteira da função onde está `expression`, copiada sem
  mudar nada; `expression` precisa aparecer dentro dela;
- `trigger`: a condição concreta sobre as entradas ou o estado que leva ao
  comportamento errado, escrita como expressão Python sobre os nomes da função
  (por exemplo `len(xs) == 0` ou `k > len(scores)`).
Se não conseguir copiar a linha ou escrever a condição, não reporte o achado.
"""


def _quoted_evidence(prompt: str) -> str:
    prompt = _swap("A14", prompt, "## SAÍDA: JSON válido", _QUOTED_EVIDENCE + "\n## SAÍDA: JSON válido")
    return _swap("A14", prompt, '"line": 0,',
                 '"line": 0,\n'
                 '        "quoted_line": "<linha inteira copiada da função>",\n'
                 '        "trigger": "<condição sobre as entradas que leva ao erro>",')
```

E no dicionário:

```python
VARIANTS: dict[str, Callable[[str], str]] = {"A1": _report_without_context, "A2": _input_checklist, "A3": _ranked,
                                             "A6": _any_wrong_behaviour, "A7": _reason_first,
                                             "A8": _worked_examples, "A9": _cause_and_crash,
                                             "A10": _keep_docstring, "A11": _file_context,
                                             "A12": _repo_callers, "A14": _quoted_evidence}
```

Em `src/research_pipeline/llm/schema.py`, substituir `v2_findings_schema` inteira:

```python
def v2_findings_schema(variants: tuple[str, ...] = ()) -> dict:
    """The V2 schema with the fields some prompt variants ask for (A7: ``analysis``, A9: ``crash_expression``,
    A14: ``quoted_line`` and ``trigger``)."""
    schema = deepcopy(V2_FINDINGS_JSON_SCHEMA)
    body = schema["schema"]
    metadata = body["properties"]["findings"]["items"]["properties"]["metadata"]
    extra = [*(["crash_expression"] if "A9" in variants else []),
             *(["quoted_line", "trigger"] if "A14" in variants else [])]
    for name in extra:
        metadata["properties"][name] = {"type": "string"}
        metadata["required"].append(name)
    if "A7" in variants:
        # Declared first so the model writes its analysis before committing to findings.
        body["properties"] = {"analysis": {"type": "string"}, **body["properties"]}
        body["required"] = ["analysis", *body["required"]]
    return schema
```

Em `src/research_pipeline/llm/findings.py`, no dicionário `metadata` de `finding_from_dict`, logo depois da linha de `crash_expression`:

```python
            "quoted_line": str(metadata_raw.get("quoted_line", "")),
            "trigger": str(metadata_raw.get("trigger", "")),
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_prompt_variants.py -q`
Expected: `22 passed`.

- [ ] **Passo 5: ponto de parada (sem commit)**

Mostrar o diff à Fernanda; não commitar.

---

### Tarefa 2: pool de exemplos com exclusão por projeto

**Files:**
- Create: `src/research_pipeline/llm/example_pool.py`
- Test: `tests/test_example_pool.py`

**Interfaces:**
- Consumes: `preprocess_file(path) -> list[CodeUnit]` (`research_pipeline.preprocess`); `should_reach_esbmc(item: dict) -> bool | None` (`research_pipeline.v2_evaluator`).
- Produces:
  - `MAX_EXAMPLE_SOURCE_CHARS = 2_500`, `MAX_EFFECT_CHARS = 200`
  - `@dataclass(frozen=True) class Example: id: str; project: str; file_stem: str; unit: CodeUnit; expression: str; crash_expressions: tuple[str, ...]; verifiable: bool; effect: str; tokens: frozenset[str]`
  - `@dataclass(frozen=True) class ExamplePool: examples: tuple[Example, ...]; project_by_stem: dict[str, str]`
  - `code_tokens(source: str) -> frozenset[str]`
  - `similarity(a: frozenset[str], b: frozenset[str]) -> float`
  - `load_example_pool(ground_truth: Path, sources_dir: Path | None = None) -> ExamplePool`
  - `select_examples(pool: ExamplePool, unit: CodeUnit, k: int) -> list[Example]`

- [ ] **Passo 1: testes que falham** (`tests/test_example_pool.py`)

```python
import json
from pathlib import Path

from research_pipeline.llm.example_pool import code_tokens, load_example_pool, select_examples, similarity
from research_pipeline.preprocess import preprocess_file

SOURCES = {
    "a_1": ("alpha", "excecao_local", "first", "def first(xs, k):\n    return xs[k - 1]\n", "xs[k - 1]"),
    "a_2": ("alpha", "excecao_local", "last", "def last(items, n):\n    return items[n + 1]\n", "items[n + 1]"),
    "b_1": ("beta", "excecao_local", "pick", "def pick(values, i):\n    return values[i + 1]\n", "values[i + 1]"),
    "c_1": ("gamma", "resultado_errado", "greet", "def greet(name):\n    return 'Olá, ' + name.upper()\n",
            "name.upper()"),
    "d_1": ("delta", "incerto", "odd", "def odd(x):\n    return x % 2\n", "x % 2"),
    "e_1": ("epsilon", "excecao_local", "big", "def big(x):\n" + "    x = x + 1\n" * 400 + "    return x\n", "x + 1"),
}


def _dataset(tmp_path: Path) -> Path:
    sources = tmp_path / "funcao_com_bug"
    sources.mkdir()
    items = []
    for item_id, (project, kind, function, source, expression) in SOURCES.items():
        (sources / f"{item_id}.py").write_text(source, encoding="utf-8")
        items.append({"id": item_id, "file": f"{item_id}.py", "function": function, "expression": expression,
                      "failure_kind": kind, "provenance": {"project": project}})
    items[0]["failure_kind_note"] = "IndexError com xs vazio"
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": items}), encoding="utf-8")
    return ground_truth


def _unit_of(ground_truth: Path, stem: str):
    return preprocess_file(ground_truth.parent / "funcao_com_bug" / f"{stem}.py")[0]


def test_pool_skips_uncertain_labels_and_long_functions(tmp_path: Path) -> None:
    pool = load_example_pool(_dataset(tmp_path))
    assert [e.id for e in pool.examples] == ["a_1", "a_2", "b_1", "c_1"]
    assert pool.project_by_stem["d_1"] == "delta" and pool.project_by_stem["e_1"] == "epsilon"


def test_example_carries_its_label_and_effect(tmp_path: Path) -> None:
    examples = {e.id: e for e in load_example_pool(_dataset(tmp_path)).examples}
    assert examples["a_1"].effect == "IndexError com xs vazio" and examples["a_1"].verifiable is True
    assert examples["c_1"].verifiable is False and "nada quebra" in examples["c_1"].effect


def test_never_selects_the_bug_itself_or_its_project(tmp_path: Path) -> None:
    ground_truth = _dataset(tmp_path)
    chosen = select_examples(load_example_pool(ground_truth), _unit_of(ground_truth, "a_1"), k=5)
    assert [e.id for e in chosen] == ["b_1", "c_1"]


def test_ties_break_by_id_so_runs_repeat(tmp_path: Path) -> None:
    ground_truth = _dataset(tmp_path)
    pool = load_example_pool(ground_truth)
    unit = _unit_of(ground_truth, "c_1")
    assert [e.id for e in select_examples(pool, unit, k=3)] == ["a_2", "b_1", "a_1"]
    assert select_examples(pool, unit, k=3) == select_examples(pool, unit, k=3)


def test_a_file_outside_the_ground_truth_is_ranked_by_similarity_only(tmp_path: Path) -> None:
    pool = load_example_pool(_dataset(tmp_path))
    other = tmp_path / "novo.py"
    other.write_text("def g(seq, j):\n    return seq[j - 1]\n", encoding="utf-8")
    assert [e.id for e in select_examples(pool, preprocess_file(other)[0], k=2)] == ["a_1", "a_2"]


def test_tokens_and_similarity_edge_cases() -> None:
    assert code_tokens("def (:") == frozenset()
    assert similarity(frozenset(), frozenset()) == 0.0
    assert "ast:Subscript" in code_tokens("def f(xs):\n    return xs[0]\n")
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_example_pool.py -q`
Expected: erro de coleta `ModuleNotFoundError: No module named 'research_pipeline.llm.example_pool'`.

- [ ] **Passo 3: implementação** (`src/research_pipeline/llm/example_pool.py`)

```python
"""Real bugs shown as few-shot examples (variant A13): the most similar ones, never from the analysed bug's project."""

from __future__ import annotations

import ast
import json
import textwrap
from dataclasses import dataclass
from pathlib import Path

from ..models import CodeUnit
from ..preprocess import preprocess_file
from ..v2_evaluator import should_reach_esbmc

MAX_EXAMPLE_SOURCE_CHARS = 2_500
MAX_EFFECT_CHARS = 200
_COMMON_NODES = {"Name", "Attribute", "Constant", "Call", "Expr", "Assign"}
_EFFECT = {
    "excecao_local": "levanta exceção dentro da função",
    "excecao_modelavel": "levanta exceção numa chamada cuja regra depende só dos argumentos",
    "excecao_nao_modelavel": "levanta exceção que depende do ambiente ou de biblioteca",
    "resultado_errado": "devolve valor errado; nada quebra",
}


@dataclass(frozen=True)
class Example:
    id: str
    project: str
    file_stem: str
    unit: CodeUnit
    expression: str
    crash_expressions: tuple[str, ...]
    verifiable: bool
    effect: str
    tokens: frozenset[str]


@dataclass(frozen=True)
class ExamplePool:
    examples: tuple[Example, ...]
    # Every labelled bug, including those left out of ``examples``, so the project exclusion covers all of them.
    project_by_stem: dict[str, str]


def code_tokens(source: str) -> frozenset[str]:
    """Identifiers plus the less common AST node kinds: what two functions that do similar things share."""
    try:
        tree = ast.parse(textwrap.dedent(source))
    except SyntaxError:
        return frozenset()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.arg):
            out.add(node.arg)
        kind = type(node).__name__
        if isinstance(node, (ast.expr, ast.stmt, ast.operator, ast.cmpop)) and kind not in _COMMON_NODES:
            out.add(f"ast:{kind}")
    return frozenset(out)


def similarity(a: frozenset[str], b: frozenset[str]) -> float:
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def _project(item: dict) -> str:
    return str(item.get("provenance", {}).get("project", "")).strip().lower()


def _unit_for(item: dict, sources_dir: Path) -> CodeUnit | None:
    path = sources_dir / item["file"]
    if not path.exists():
        return None
    units = {unit.qualname: unit for unit in preprocess_file(path)}
    names = [part.strip() for part in str(item.get("function", "")).split("/") if part.strip()]
    return next((units[name] for name in names if name in units), None)


def load_example_pool(ground_truth: Path, sources_dir: Path | None = None) -> ExamplePool:
    """Labelled bugs whose function is short enough to show; ``sources_dir`` defaults to ``funcao_com_bug`` beside it."""
    ground_truth = Path(ground_truth)
    items = json.loads(ground_truth.read_text(encoding="utf-8"))["items"]
    sources_dir = sources_dir or ground_truth.parent / "funcao_com_bug"
    examples = []
    for item in items:
        verifiable = should_reach_esbmc(item)
        if verifiable is None or not item.get("expression"):
            continue
        unit = _unit_for(item, sources_dir)
        if unit is None or len(unit.source) > MAX_EXAMPLE_SOURCE_CHARS:
            continue
        effect = str(item.get("failure_kind_note") or _EFFECT[item["failure_kind"]])[:MAX_EFFECT_CHARS]
        examples.append(Example(
            id=str(item["id"]), project=_project(item), file_stem=Path(item["file"]).stem, unit=unit,
            expression=str(item["expression"]), crash_expressions=tuple(item.get("crash_expressions", [])),
            verifiable=verifiable, effect=effect, tokens=code_tokens(unit.source)))
    project_by_stem = {Path(item["file"]).stem: _project(item) for item in items}
    return ExamplePool(tuple(sorted(examples, key=lambda e: e.id)), project_by_stem)


def select_examples(pool: ExamplePool, unit: CodeUnit, k: int) -> list[Example]:
    """The k most similar examples, never the analysed file's bug nor any bug of its project; ties by id."""
    stem = unit.path.stem
    project = pool.project_by_stem.get(stem)
    allowed = [e for e in pool.examples if e.file_stem != stem and (project is None or e.project != project)]
    target = code_tokens(unit.source)
    return sorted(allowed, key=lambda e: (-similarity(target, e.tokens), e.id))[:k]
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_example_pool.py -q`
Expected: `6 passed`.

- [ ] **Passo 5: ponto de parada (sem commit)**

Conferir no gabarito real, sem LLM: `PYTHONPATH=src .venv/bin/python -c "from pathlib import Path; from research_pipeline.llm.example_pool import load_example_pool; p = load_example_pool(Path('dataset/bugs_reais/ground_truths.json')); print(len(p.examples), len(p.project_by_stem))"`. Expected: `227 289` com o gabarito de 16/10, ou números próximos se o item 1 mudar `failure_kind`. Não commitar.

---

### Tarefa 3: variante A13 no prompt e na CLI, impressão digital

**Files:**
- Modify: `src/research_pipeline/llm/prompt_variants.py`
- Modify: `src/research_pipeline/llm/prompts.py`
- Modify: `src/main.py`
- Test: `tests/test_prompt_variants.py`, `tests/test_main_v2.py`

**Interfaces:**
- Consumes: `ExamplePool`, `Example`, `select_examples`, `load_example_pool` (Tarefa 2); `"A14"` (Tarefa 1).
- Produces: variante `"A13"` em `VARIANTS`; `set_example_pool(pool: ExamplePool | None, k: int = 3) -> None` em `prompts.py`; `build_user_prompt(unit, *, include_smells=True, v2_variants=())` acrescenta `<UNTRUSTED_EXEMPLOS>` quando `"A13" in v2_variants` e levanta `ValueError` com "A13" na mensagem sem pool; CLI `--example-pool JSON` e `--example-k K`; `config["example_pool"]` e `config["example_k"]` só com A13; `_v2_fingerprint` ganha `detector_system_prompt` (A13 ou A14) e `example_pool` (A13).

- [ ] **Passo 1: testes que falham**

Em `tests/test_prompt_variants.py`, acrescentar aos imports:

```python
from research_pipeline.llm.example_pool import Example, ExamplePool, code_tokens
from research_pipeline.llm.prompts import set_example_pool
```

E ao fim do arquivo:

```python
def _example(item_id: str, project: str, source: str, name: str, expression: str) -> Example:
    return Example(id=item_id, project=project, file_stem=item_id, unit=_unit(Path(f"{item_id}.py"), source, name=name),
                   expression=expression, crash_expressions=(), verifiable=True,
                   effect="levanta exceção dentro da função", tokens=code_tokens(source))


def test_a13_shows_examples_from_other_projects_only() -> None:
    pool = ExamplePool(
        examples=(_example("a_2", "alpha", "def last(items, n):\n    return items[n + 1]\n", "last", "items[n + 1]"),
                  _example("b_1", "beta", "def pick(values, i):\n    return pick(values[i + 1:], i)\n", "pick",
                           "pick(values[i + 1:], i)")),
        project_by_stem={"a_1": "alpha", "a_2": "alpha", "b_1": "beta"})
    unit = _unit(Path("a_1.py"), "def first(xs, k):\n    return xs[k - 1]\n", name="first")
    set_example_pool(pool, k=3)
    try:
        prompt = build_user_prompt(unit, include_smells=False, v2_variants=("A13",))
    finally:
        set_example_pool(None)
    block = prompt[prompt.index("<UNTRUSTED_EXEMPLOS>"):prompt.index("</UNTRUSTED_EXEMPLOS>")]
    assert "items[n + 1]" not in block
    assert "Bug corrigido pelos mantenedores: `target_function(values[i + 1:], i)`" in block
    assert "def target_function(values, i):" in block and "verifiable: true" in block
    assert "## EXEMPLOS DE BUGS REAIS" in apply_variants(BASE, ("A13",))


def test_a13_without_a_pool_fails_loudly() -> None:
    set_example_pool(None)
    unit = _unit(Path("m.py"), "def f(x):\n    return x\n")
    with pytest.raises(ValueError, match="A13"):
        build_user_prompt(unit, include_smells=False, v2_variants=("A13",))


def test_a_pool_without_a13_adds_no_examples() -> None:
    pool = ExamplePool(examples=(_example("b_1", "beta", "def g(x):\n    return x[0]\n", "g", "x[0]"),),
                       project_by_stem={})
    set_example_pool(pool)
    try:
        prompt = build_user_prompt(_unit(Path("m.py"), "def f(x):\n    return x\n"), include_smells=False,
                                   v2_variants=("A1", "A2"))
    finally:
        set_example_pool(None)
    assert "UNTRUSTED_EXEMPLOS" not in prompt
```

Em `tests/test_main_v2.py`, acrescentar ao fim:

```python
def _pool(tmp_path: Path) -> Path:
    sources = tmp_path / "pool" / "funcao_com_bug"
    sources.mkdir(parents=True)
    (sources / "x_1.py").write_text("def pick(values, i):\n    return values[i + 1]\n", encoding="utf-8")
    ground_truth = tmp_path / "pool" / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [
        {"id": "x_1", "file": "x_1.py", "function": "pick", "expression": "values[i + 1]",
         "failure_kind": "excecao_local", "provenance": {"project": "outro"}}]}), encoding="utf-8")
    return ground_truth


def _detection_args(source: Path, out: Path, *extra: str):
    return main.build_parser().parse_args(["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
                                           "--output-dir", str(out), *extra])


def test_a13_loads_the_example_pool_and_records_it(tmp_path: Path, monkeypatch) -> None:
    from research_pipeline.llm.prompts import set_example_pool

    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    ground_truth = _pool(tmp_path)
    out = tmp_path / "out"
    args = _detection_args(source, out, "--v2-variants", "A1,A2,A13", "--example-pool", str(ground_truth))
    try:
        assert main.mode_v2(args) == 0
    finally:
        set_example_pool(None)
    config = json.loads((out / "v2_verify_report.json").read_text())["config"]
    assert config["example_pool"] == str(ground_truth.resolve()) and config["example_k"] == 3
    fingerprint = json.loads((out / "v2_checkpoint.json").read_text())["fingerprint"]
    assert "example_pool" in fingerprint and "detector_system_prompt" in fingerprint


def test_a13_with_a_missing_pool_exits_with_error(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    args = _detection_args(source, tmp_path / "out", "--v2-variants", "A13",
                           "--example-pool", str(tmp_path / "nao_existe.json"))
    assert main.mode_v2(args) == 1


def test_fingerprint_keeps_its_keys_for_earlier_variants() -> None:
    keys = set(main._v2_fingerprint({"v2_variants": ["A1", "A2"]}, []))
    assert keys == {"config", "sources", "detector_prompt", "detector_schema", "spec_prompt"}
    assert "detector_system_prompt" in main._v2_fingerprint({"v2_variants": ["A1", "A2", "A14"]}, [])
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_prompt_variants.py tests/test_main_v2.py -q`
Expected: erro de coleta em `test_prompt_variants.py` (`ImportError: cannot import name 'set_example_pool'`); em `test_main_v2.py`, falhas por argumento desconhecido `--example-pool` (`SystemExit: 2`) e por `detector_system_prompt` ausente.

- [ ] **Passo 3: implementação**

Em `src/research_pipeline/llm/prompt_variants.py`, antes de `_QUOTED_EVIDENCE`:

```python
_REAL_EXAMPLES = """## EXEMPLOS DE BUGS REAIS

Depois da função vem um bloco `UNTRUSTED_EXEMPLOS` com funções de outros projetos
e o bug real que os mantenedores corrigiram em cada uma: a expressão que a correção
mudou e, quando houve exceção, onde ela estoura. Use-os para calibrar que expressão
apontar em `expression`. Eles não são a função analisada: não reporte achados sobre
eles e não suponha que a função analisada tenha o mesmo bug.
"""


def _real_examples(prompt: str) -> str:
    """The examples themselves depend on the function; ``build_user_prompt`` adds them."""
    return _swap("A13", prompt, "## SAÍDA: JSON válido", _REAL_EXAMPLES + "\n## SAÍDA: JSON válido")
```

E no dicionário, `"A13": _real_examples,` antes de `"A14": _quoted_evidence`.

Em `src/research_pipeline/llm/prompts.py`, acrescentar aos imports:

```python
from .example_pool import Example, ExamplePool, select_examples
```

Em `build_user_prompt`, depois da linha do A12:

```python
        + (_examples_section(unit) if "A13" in v2_variants else "")
```

E depois de `_caller_context_section`:

```python
_example_pool: ExamplePool | None = None
_example_k = 3


def set_example_pool(pool: ExamplePool | None, k: int = 3) -> None:
    """A13 takes k examples per function from this pool; None turns the pool off."""
    global _example_pool, _example_k
    _example_pool, _example_k = pool, k


def _examples_section(unit: CodeUnit) -> str:
    if _example_pool is None:
        raise ValueError("variant A13 needs an example pool: set_example_pool() or --example-pool")
    chosen = select_examples(_example_pool, unit, _example_k)
    if not chosen:
        return ""
    body = "\n\n".join(_render_example(number, example) for number, example in enumerate(chosen, 1))
    return f"<UNTRUSTED_EXEMPLOS>\n{body}\n</UNTRUSTED_EXEMPLOS>\n\n"


def _renamed(text: str, name: str) -> str:
    return re.sub(rf"\b{re.escape(name)}\b", "target_function", text)


def _render_example(number: int, example: Example) -> str:
    name = example.unit.name
    lines = [f"Exemplo {number}:", _source_for_llm(example.unit),
             f"Bug corrigido pelos mantenedores: `{_renamed(example.expression, name)}`"]
    if example.crash_expressions:
        lines.append(f"Onde a exceção estoura: `{_renamed(example.crash_expressions[0], name)}`")
    lines += [f"Efeito: {example.effect}", f"verifiable: {'true' if example.verifiable else 'false'}"]
    return "\n".join(lines)
```

Em `src/main.py`, trocar o import de `prompts` e acrescentar o do pool:

```python
from research_pipeline.llm.example_pool import load_example_pool
from research_pipeline.llm.prompts import load_system_prompt, set_context_sources, set_example_pool
```

Logo depois do `parser.add_argument("--v2-variants", ...)`:

```python
    parser.add_argument(
        "--example-pool",
        default=str(REPO_ROOT / "dataset/bugs_reais/ground_truths.json"),
        metavar="JSON",
        help="Variante A13: gabarito de onde saem os exemplos (funções em funcao_com_bug/ ao lado dele).",
    )
    parser.add_argument("--example-k", type=_positive_int, default=3, metavar="K",
                        help="Variante A13: quantos exemplos por função (padrão: 3).")
```

Substituir `_v2_fingerprint` inteira:

```python
def _v2_fingerprint(config: dict, input_paths: list[Path]) -> dict:
    variants = tuple(config.get("v2_variants", ()))
    fingerprint = {
        "config": config,
        "sources": {
            str(path.resolve()): sha256(path.read_bytes()).hexdigest()
            for path in input_paths
        },
        "detector_prompt": sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/system_prompt_v2.txt").read_bytes()
        ).hexdigest(),
        "detector_schema": sha256(json.dumps(v2_findings_schema(variants), sort_keys=True).encode()).hexdigest(),
        "spec_prompt": sha256(
            (REPO_ROOT / "src/research_pipeline/prompts/input_spec_prompt.txt").read_bytes()
        ).hexdigest(),
    }
    # Only for A13/A14, so checkpoints of earlier variants (the paused final run) still resume.
    if {"A13", "A14"} & set(variants):
        system = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants)
        fingerprint["detector_system_prompt"] = sha256(system.encode()).hexdigest()
    if "A13" in variants:
        fingerprint["example_pool"] = sha256(Path(config["example_pool"]).read_bytes()).hexdigest()
    return fingerprint
```

Em `mode_v2`, trocar o bloco de `set_context_sources` até o `except`:

```python
        context_sources = args.context_sources or args.verification_sources
        set_context_sources(Path(context_sources) if context_sources else None)
        if "A13" in variants:
            set_example_pool(load_example_pool(Path(args.example_pool)), k=args.example_k)
        else:
            set_example_pool(None)
        synthesizer = _build_synthesizer(args, synth_backend, synth_model, openai_key, google_key)
    except (ValueError, OSError, KeyError) as exc:
        print(f"Erro: {exc}", file=sys.stderr)
        return 1
```

E logo depois do dicionário `config = {...}` em `mode_v2`:

```python
    if "A13" in variants:
        config["example_pool"] = str(Path(args.example_pool).resolve())
        config["example_k"] = args.example_k
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_prompt_variants.py tests/test_main_v2.py tests/test_example_pool.py -q`
Expected: todos passam (25 em `test_prompt_variants.py`, os 6 do pool e os de `test_main_v2.py` com 3 novos).

Conferir a retomada da rodada pausada, sem LLM: `PYTHONPATH=src .venv/bin/python -c "import json, sys; sys.path.insert(0, 'src'); import main; c = json.load(open('artifacts/v2/final-2026-10-15-codex/v2_checkpoint.json'))['fingerprint']; print(sorted(c) == sorted(main._v2_fingerprint(c['config'], [])) , c['detector_schema'] == main._v2_fingerprint(c['config'], [])['detector_schema'])"`. Expected: `True True`.

- [ ] **Passo 5: ponto de parada (sem commit)**

Mostrar o diff à Fernanda; não commitar.

---

### Tarefa 4: inspeção dos prompts sem LLM e backend escolhível nas rodadas

**Files:**
- Create: `scripts/print_detection_prompt.py`
- Modify: `scripts/run_detection_variants.sh`
- Test: `tests/test_print_detection_prompt.py`

**Interfaces:**
- Consumes: `load_system_prompt`, `build_user_prompt`, `set_context_sources`, `set_example_pool` (`prompts.py`); `load_example_pool` (Tarefa 2); `preprocess_file`.
- Produces: `render(paths: list[str], variants: tuple[str, ...], *, function: str | None = None) -> tuple[str, list[tuple[str, str]]]`; `main(argv: list[str] | None = None) -> int` (0 com pelo menos uma função, 1 sem nenhuma); variáveis `BACKEND` e `MODEL` em `run_detection_variants.sh`.

- [ ] **Passo 1: testes que falham** (`tests/test_print_detection_prompt.py`)

```python
import importlib.util
import json
import subprocess
import urllib.request
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location("pdp", Path(__file__).parents[1] / "scripts/print_detection_prompt.py")
pdp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pdp)


@pytest.fixture
def no_llm(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("print_detection_prompt must not call an LLM")

    monkeypatch.setattr(urllib.request, "urlopen", refuse)
    monkeypatch.setattr(subprocess, "run", refuse)
    monkeypatch.setattr(subprocess, "Popen", refuse)


def test_prints_system_and_user_prompts(tmp_path: Path, capsys, no_llm) -> None:
    source = tmp_path / "m.py"
    source.write_text("def head(xs):\n    return xs[0]\n", encoding="utf-8")
    assert pdp.main(["--input", str(source), "--v2-variants", "A1,A2,A14"]) == 0
    captured = capsys.readouterr()
    assert "## EVIDÊNCIA CITADA" in captured.out and "return xs[0]" in captured.out
    assert "=== m.py::head ===" in captured.out and "tokens" in captured.err


def test_writes_one_file_per_function_with_a13(tmp_path: Path, no_llm) -> None:
    sources = tmp_path / "funcao_com_bug"
    sources.mkdir()
    (sources / "x_1.py").write_text("def pick(values, i):\n    return values[i + 1]\n", encoding="utf-8")
    ground_truth = tmp_path / "ground_truths.json"
    ground_truth.write_text(json.dumps({"items": [
        {"id": "x_1", "file": "x_1.py", "function": "pick", "expression": "values[i + 1]",
         "failure_kind": "excecao_local", "provenance": {"project": "outro"}}]}), encoding="utf-8")
    target = tmp_path / "m.py"
    target.write_text("def head(xs, k):\n    return xs[k + 1]\n", encoding="utf-8")
    out = tmp_path / "out"
    assert pdp.main(["--input", str(target), "--v2-variants", "A13", "--example-pool", str(ground_truth),
                     "--out", str(out)]) == 0
    assert "## EXEMPLOS DE BUGS REAIS" in (out / "system.txt").read_text(encoding="utf-8")
    assert "<UNTRUSTED_EXEMPLOS>" in (out / "m.py__head.txt").read_text(encoding="utf-8")


def test_no_matching_function_returns_one(tmp_path: Path, no_llm) -> None:
    source = tmp_path / "m.py"
    source.write_text("def head(xs):\n    return xs[0]\n", encoding="utf-8")
    assert pdp.main(["--input", str(source), "--function", "nada"]) == 1
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_print_detection_prompt.py -q`
Expected: erro de coleta `FileNotFoundError` (o script ainda não existe).

- [ ] **Passo 3: implementação**

`scripts/print_detection_prompt.py`:

```python
"""Print the V2 detection prompts (system and user) without calling any LLM.

Usage: .venv/bin/python scripts/print_detection_prompt.py --input FILE_OR_DIR... [--v2-variants A1,A2,A13]
       [--example-pool dataset/bugs_reais/ground_truths.json] [--example-k 3] [--context-sources DIR]
       [--function QUALNAME] [--out DIR]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from research_pipeline.llm.example_pool import load_example_pool  # noqa: E402
from research_pipeline.llm.prompts import (  # noqa: E402
    build_user_prompt,
    load_system_prompt,
    set_context_sources,
    set_example_pool,
)
from research_pipeline.preprocess import preprocess_file  # noqa: E402

CHARS_PER_TOKEN = 4  # rough, only to compare the variants' size


def _python_files(paths: list[str]) -> list[Path]:
    out: list[Path] = []
    for raw in paths:
        path = Path(raw)
        out.extend(sorted(path.rglob("*.py")) if path.is_dir() else [path])
    return out


def render(paths: list[str], variants: tuple[str, ...], *,
           function: str | None = None) -> tuple[str, list[tuple[str, str]]]:
    system = load_system_prompt(include_smells=False, v2_detection=True, v2_variants=variants)
    users = [(f"{path.name}::{unit.qualname}", build_user_prompt(unit, include_smells=False, v2_variants=variants))
             for path in _python_files(paths) for unit in preprocess_file(path)
             if function is None or unit.qualname == function]
    return system, users


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", nargs="+", required=True)
    parser.add_argument("--v2-variants", default="")
    parser.add_argument("--example-pool", default=str(REPO_ROOT / "dataset/bugs_reais/ground_truths.json"))
    parser.add_argument("--example-k", type=int, default=3)
    parser.add_argument("--context-sources", default=None)
    parser.add_argument("--function", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    variants = tuple(v for v in args.v2_variants.split(",") if v)
    set_context_sources(Path(args.context_sources) if args.context_sources else None)
    if "A13" in variants:
        set_example_pool(load_example_pool(Path(args.example_pool)), k=args.example_k)
    try:
        system, users = render(args.input, variants, function=args.function)
    finally:
        set_context_sources(None)
        set_example_pool(None)
    if not users:
        print("Nenhuma função encontrada.", file=sys.stderr)
        return 1
    if args.out:
        out = Path(args.out)
        out.mkdir(parents=True, exist_ok=True)
        (out / "system.txt").write_text(system, encoding="utf-8")
        for label, user in users:
            (out / f"{label.replace('::', '__')}.txt").write_text(user, encoding="utf-8")
    else:
        print(f"=== system ===\n{system}\n")
        for label, user in users:
            print(f"=== {label} ===\n{user}\n")
    total = sum(len(system) + len(user) for _, user in users)
    print(f"{len(users)} função(ões); cerca de {total // CHARS_PER_TOKEN} tokens de entrada no total",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

Em `scripts/run_detection_variants.sh`, trocar o comentário de uso e acrescentar as variáveis logo depois da linha `PY=...`:

```bash
# Usage: [BACKEND=google MODEL=gemini-2.5-flash] scripts/run_detection_variants.sh <tag> <sample.json> <variant>...
```

```bash
BACKEND=${BACKEND:-claude_cli}
MODEL=${MODEL:-claude-sonnet-5-5}
```

E na chamada do `main.py`, trocar `--backend claude_cli --model claude-sonnet-5-5` por:

```bash
      --backend "$BACKEND" --model "$MODEL" "${flags[@]}" "${resume[@]}" \
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_print_detection_prompt.py -q`
Expected: `3 passed`.

Run: `bash -n scripts/run_detection_variants.sh && grep -c '"$BACKEND"' scripts/run_detection_variants.sh`
Expected: `1` (não rodar o script: ele chama LLM).

Inspeção real, sem LLM: `.venv/bin/python scripts/print_detection_prompt.py --input dataset/bugs_reais/funcao_com_bug/bip_pandas_84.py --v2-variants A1,A2,A13,A14 --context-sources dataset/bugs_reais/arquivo_com_bug`. Expected: o bloco `<UNTRUSTED_EXEMPLOS>` com 3 exemplos, nenhum com projeto pandas, e o total de tokens no stderr.

- [ ] **Passo 5: ponto de parada (sem commit)**

Mostrar à Fernanda a saída da inspeção do `bip_pandas_84`; não commitar.

---

### Tarefa 5: composição, suíte e registro

**Files:**
- Test: `tests/test_prompt_variants.py`
- Modify: `docs/projeto/PLANO_GERAL_2026-10-15.md`
- Modify: `docs/experimentos/README.md`

**Interfaces:**
- Consumes: A9 (existente), A13 e A14 (Tarefas 1 e 3).
- Produces: teste de composição; registro do item 4 sem rodada.

- [ ] **Passo 1: teste de composição** (acrescentar ao fim de `tests/test_prompt_variants.py`)

```python
def test_new_variants_compose_with_a5_and_a9() -> None:
    changed = apply_variants(BASE, ("A1", "A2", "A9", "A13", "A14"))
    for marker in ("## PARTIÇÃO DE ENTRADAS", "## ONDE O BUG NASCE", "## EXEMPLOS DE BUGS REAIS",
                   "## EVIDÊNCIA CITADA", '"crash_expression"', '"quoted_line"', '"trigger"'):
        assert marker in changed
    assert changed.count("## SAÍDA: JSON válido") == 1
    assert changed.index("## EVIDÊNCIA CITADA") < changed.index("## SAÍDA")
```

- [ ] **Passo 2: rodar**

Run: `.venv/bin/python -m pytest tests/test_prompt_variants.py -q`
Expected: `26 passed`. Este teste já nasce passando: ele protege a composição contra uma variante futura que apague a âncora de outra.

- [ ] **Passo 3: suíte completa e lint**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: tudo passa, com 19 testes a mais que antes da Tarefa 1 (3 na Tarefa 1, 6 na Tarefa 2, 6 na Tarefa 3, 3 na Tarefa 4, 1 na Tarefa 5).

Run: `pylint src/research_pipeline/llm/example_pool.py src/research_pipeline/llm/prompt_variants.py src/research_pipeline/llm/prompts.py scripts/print_detection_prompt.py --disable=C,R`
Expected: nenhum erro (`E`) nem aviso novo em linha tocada; corrigir o que aparecer antes de seguir.
Em 16/10 o `pylint` não estava no PATH do WSL nem no `.venv`; se continuar assim, perguntar à Fernanda antes de instalar e registrar no README que o lint não rodou.

- [ ] **Passo 4: registro**

Em `docs/projeto/PLANO_GERAL_2026-10-15.md`, na tabela, trocar a linha do item 4 por:

```markdown
| 4 | Variantes de prompt | implementado (A13, A14, inspeção sem LLM); comparação no item 6 |
```

E acrescentar ao fim da seção "## 4. Variantes de prompt":

```markdown
- [x] Spec `docs/superpowers/specs/2026-10-16-variantes-prompt-design.md`, plano `docs/superpowers/plans/2026-10-16-variantes-prompt.md`.
- [x] A13 (exemplos reais por similaridade, sem o projeto do bug) e A14 (linha citada e condição de disparo), com testes.
- [x] `scripts/print_detection_prompt.py` (prompts sem LLM) e `BACKEND`/`MODEL` em `run_detection_variants.sh`.
- Para o item 6: comparar A5, A5+A9, A5+A13, A5+A14 com `BACKEND=google MODEL=gemini-2.5-flash`.
```

Em `docs/experimentos/README.md`, acrescentar ao fim:

```markdown
## Item 4 (16/10): variantes A13 e A14, sem rodada

Mudança no pipeline (sem commit até a data): `llm/example_pool.py` (pool do gabarito, similaridade
Jaccard por AST, exclusão do projeto do bug), variantes A13 e A14 em `llm/prompt_variants.py`, campos
`quoted_line` e `trigger` no esquema com A14, `--example-pool`/`--example-k` no `main.py`, impressão
digital ampliada só para A13 e A14, `scripts/print_detection_prompt.py` e `BACKEND`/`MODEL` em
`scripts/run_detection_variants.sh`.

- **Sem rodada:** nenhuma chamada a LLM. A comparação fica para o item 6 do PLANO_GERAL.
- **Testes:** suíte rápida passando (anotar o total do Passo 3).
```

- [ ] **Passo 5: ponto de parada (sem commit)**

Mostrar à Fernanda o diff completo e o total da suíte; não commitar.
