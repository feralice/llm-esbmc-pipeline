# Oráculo de valor errado no harness: plano de implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** permitir que uma hipótese de valor errado seja confirmada: o LLM escreve a pós-condição do resultado, o harness a coloca como `assert` depois da chamada à função real, o ESBMC procura a violação, o replay no CPython confirma no código original, e a versão corrigida, com a mesma entrada, não pode violar (senão `PROPERTY_REJECTED`).

**Architecture:** a hipótese ganha `oracle = "value"` (entrada pela variante de detecção `A15`). A chamada de spec já existente pede também `returns` e `postcondition`, validadas por um subconjunto seguro de AST em `verify/spec.py`. `verify/render.py` escreve `_esbmc_result = <chamada>` e `assert <propriedade>` no fim do driver e grava `Program.property_line`. O replay reconhece a violação pela `AssertionError` do driver nessa linha. Um módulo novo, `verify/value_oracle.py`, lê o ESBMC pela linha do `assert`, decide o veredito, troca a função alvo pela da versão corrigida e roda o controle. `verify/loop.py` liga tudo; roteamento e métrica contam `VALUE_CONFIRMED` à parte.

**Tech Stack:** Python 3.12 do `.venv`, `ast`, `dataclasses`, pytest com `monkeypatch`; replay pelo CPython em subprocesso (já existente); nenhum ESBMC ou LLM real nos testes.

**Spec:** `docs/superpowers/specs/2026-10-16-oraculo-valor-design.md`

## Global Constraints

- Hipóteses de exceção (`oracle == ""`) não mudam: mesmo `hypothesis_id`, mesmo prompt, mesmo harness, mesmo replay. Nenhum teste existente é editado; a suíte inteira continua passando.
- A versão corrigida nunca entra em prompt: é lida em `run_verify` só para hipóteses de valor e usada depois da resposta do LLM.
- Testes com LLM falso e ESBMC falso (`monkeypatch` de `esbmc_run.run_esbmc_direct` e de `loop.convert`); o replay pode rodar o CPython de verdade, como em `tests/test_verify_replay.py`.
- Nenhuma rodada, medição ou chamada a LLM pago: a medição é do item 6.
- Nomes de veredito novos: `VALUE_VIOLATION`, `VALUE_CONFIRMED`, `PROPERTY_REJECTED` (conferidos contra todos os existentes na Tarefa 5).
- Sem travessão em texto; sem commit sem a Fernanda pedir (os passos de commit viram "ponto de parada").
- Teste de um arquivo: `.venv/bin/python -m pytest tests/<arquivo> -q`. Suíte: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`.
- Trabalhar direto em `master` (regra do repo, sobrepõe a de branch).

## Review Focus

1. **Vazamento da versão corrigida para o LLM.** Nenhum prompt (sistema ou usuário) pode conter texto da corrigida. Teste: `test_the_fixed_version_never_reaches_the_llm` (Tarefa 6).
2. **Outra `AssertionError` contada como violação da propriedade** (um `assert` do próprio código alvo ou de um stub). Só a do driver na `property_line` conta. Teste: `test_an_assert_inside_the_target_is_not_the_property` (Tarefa 4); no ESBMC, `test_esbmc_hits_only_the_assert_at_the_property_line` (Tarefa 5).
3. **Controle que "passa" sem ter rodado.** Execução descartada (suposição ou tempo) ou exceção na corrigida não pode virar `VALUE_CONFIRMED`. Testes: `test_a_discarded_fixed_run_is_unavailable_with_a_property` (Tarefa 4) e a tabela `test_control_needs_a_clean_run_of_the_fixed_version` (Tarefa 5).
4. **Linha da propriedade desalinhada ou `return` cortado.** Cada cópia (ESBMC e replay) tem a sua linha do `assert`, porque `split_conditional_assignments` cresce só a cópia do ESBMC; o ESBMC é lido pela `property_line`, o replay pela `replay_property_line`, e o controle desloca a do replay pela diferença de tamanho da corrigida. O corte depois da suspeita não pode apagar o `return`. Testes: `test_value_driver_asserts_the_postcondition_on_the_returned_value`, `test_the_property_line_follows_each_copy_when_only_the_esbmc_copy_grows`, `test_value_hypotheses_keep_the_code_after_the_suspect` (Tarefa 3), `test_the_fixed_function_replaces_the_target_and_moves_the_property_line` (Tarefa 5).
5. **Regressão em hipóteses de exceção** (ids, prompt, worker sem `property_line`, `shape_unpacked` perdendo campos). Testes: `test_exception_hypotheses_keep_their_old_ids` (Tarefa 1), `test_shape_unpacked_keeps_the_value_fields` (Tarefa 2), `test_without_a_property_line_a_driver_assert_stays_other_failure` (Tarefa 4), `test_the_value_prompt_is_only_for_value_hypotheses` (Tarefa 6), e a suíte inteira no fim de cada tarefa.

---

### Tarefa 1: hipótese com oráculo e entrada pela variante A15

**Files:**
- Modify: `src/research_pipeline/verify/hypothesis.py`
- Modify: `src/research_pipeline/verify/candidate.py`
- Modify: `src/research_pipeline/llm/prompt_variants.py`
- Modify: `src/research_pipeline/llm/schema.py`
- Modify: `src/research_pipeline/llm/findings.py`
- Modify: `src/main.py`
- Test: `tests/test_verify_value_entry.py` (novo)

**Interfaces:**
- Produces: `VALUE_ORACLE = "value"` em `verify/hypothesis.py`; campo `BugHypothesis.oracle: str = ""`; campo `Candidate.oracle: str = ""`; variante `"A15"` em `VARIANTS`; `v2_findings_schema(("A15",))` com `metadata.failure_mode` (enum `excecao`, `resultado_errado`, `outro`); `Finding.metadata["failure_mode"]`.
- Consumes: nada novo.

- [ ] **Passo 1: testes que falham**

```python
import hashlib
from pathlib import Path

import main
from research_pipeline.llm.findings import finding_from_dict
from research_pipeline.llm.prompt_variants import apply_variants
from research_pipeline.llm.prompts import load_system_prompt
from research_pipeline.llm.schema import v2_findings_schema
from research_pipeline.models import Finding
from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis

BASE = load_system_prompt(include_smells=False, v2_detection=True)


def test_exception_hypotheses_keep_their_old_ids():
    h = BugHypothesis("a.py", "f", "x // y", line=3)
    assert h.hypothesis_id == hashlib.sha1(b"a.py|f|3|x // y").hexdigest()[:12]


def test_a_value_hypothesis_gets_its_own_id_and_round_trips():
    h = BugHypothesis("a.py", "f", "x // y", line=3, oracle=VALUE_ORACLE)
    assert h.hypothesis_id != BugHypothesis("a.py", "f", "x // y", line=3).hypothesis_id
    data = h.to_dict()
    assert data["oracle"] == "value"
    assert BugHypothesis(**{k: v for k, v in data.items() if k != "hypothesis_id"}) == h


def test_candidates_carry_the_oracle_to_the_hypothesis():
    assert Candidate.from_dict({"file": "a.py", "function": "f"}).oracle == ""
    candidate = Candidate.from_dict({"file": "a.py", "function": "f", "expression": "x", "oracle": "value"})
    assert candidate.to_dict()["oracle"] == "value"
    assert BugHypothesis.from_candidate(candidate).oracle == VALUE_ORACLE


def test_a13_asks_how_the_bug_shows_in_prompt_and_schema():
    changed = apply_variants(BASE, ("A15",))
    assert "## BUG DE RESULTADO ERRADO" in changed and '"failure_mode"' in changed
    metadata = v2_findings_schema(("A15",))["schema"]["properties"]["findings"]["items"]["properties"]["metadata"]
    assert metadata["properties"]["failure_mode"]["enum"] == ["excecao", "resultado_errado", "outro"]
    assert "failure_mode" in metadata["required"]
    assert "failure_mode" not in v2_findings_schema(())["schema"]["properties"]["findings"]["items"][
        "properties"]["metadata"]["properties"]


def test_failure_mode_is_read_from_the_metadata():
    raw = {"metadata": {"expression": "x", "failure_mode": "resultado_errado"}, "verifiable": False}
    assert finding_from_dict(raw).metadata["failure_mode"] == "resultado_errado"


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


class _WrongResultAnalyzer:
    def __init__(self, failure_mode):
        self.failure_mode = failure_mode

    def analyze(self, unit):
        return [Finding(id="w", stage="llm_analysis", finding_type="suspected_bug", category="", title="",
                        explanation="returns x for a negative x", evidence=[], verifiable=False,
                        confidence="high",
                        metadata={"expression": "x if x > 0 else x", "failure_mode": self.failure_mode})]


def _detected(tmp_path: Path, monkeypatch, failure_mode: str, variants: str) -> list:
    # One directory per run: a shared output directory would resume the previous run's checkpoint.
    work = tmp_path / f"{failure_mode}-{variants or 'base'}"
    work.mkdir()
    source = work / "m.py"
    source.write_text("def magnitude(x):\n    return x if x > 0 else x\n", encoding="utf-8")
    captured = {}

    def fake_verify(hypotheses, **kwargs):
        captured["hypotheses"] = hypotheses
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _WrongResultAnalyzer(failure_mode))
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    argv = ["--mode", "hybrid", "--input", str(source), "--output-dir", str(work / "out")]
    if variants:
        argv += ["--v2-variants", variants]
    assert main.mode_v2(main.build_parser().parse_args(argv)) == 0
    return captured["hypotheses"]


def test_with_a13_a_wrong_result_finding_becomes_a_value_hypothesis(tmp_path, monkeypatch):
    hypotheses = _detected(tmp_path, monkeypatch, "resultado_errado", "A15")
    assert [(h.function, h.oracle) for h in hypotheses] == [("magnitude", VALUE_ORACLE)]


def test_without_a13_a_wrong_result_finding_is_still_held(tmp_path, monkeypatch):
    assert _detected(tmp_path, monkeypatch, "resultado_errado", "") == []
    assert _detected(tmp_path, monkeypatch, "outro", "A15") == []
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_entry.py -q`
Expected: erro na coleta, `ImportError: cannot import name 'VALUE_ORACLE'`.

- [ ] **Passo 3: implementação**

`src/research_pipeline/verify/hypothesis.py`, depois dos imports:

```python
# A wrong-result hypothesis: nothing raises; an LLM-written postcondition decides (verify/value_oracle.py).
VALUE_ORACLE = "value"
```

Na classe, depois de `category: str = ""`:

```python
    oracle: str = ""  # "" for an exception, VALUE_ORACLE for a wrong result
```

Trocar a propriedade `hypothesis_id` e `from_candidate` por:

```python
    @property
    def hypothesis_id(self) -> str:
        parts = (self.file, self.function, str(self.line), self.suspect_expression)
        # Only a value hypothesis adds its oracle, so the ids saved before it existed stay valid.
        key = "|".join((*parts, self.oracle) if self.oracle else parts)
        return hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]

    @classmethod
    def from_candidate(cls, candidate: Candidate, line: int = 0) -> BugHypothesis:
        return cls(
            file=candidate.file,
            function=candidate.function,
            suspect_expression=candidate.expression,
            line=line,
            trigger_condition=candidate.note,
            category=candidate.category,
            oracle=candidate.oracle,
        )
```

`src/research_pipeline/verify/candidate.py`: campo novo depois de `violated_property: str = ""`:

```python
    oracle: str = ""
```

e o `return` de `from_dict` passa a ser:

```python
        return cls(str(data["file"]), str(data["function"]), str(data.get("category", "")),
                   str(data.get("expression", "")), str(data.get("note", "")),
                   str(data.get("violated_property", "")), str(data.get("oracle", "")))
```

`src/research_pipeline/llm/prompt_variants.py`, antes de `VARIANTS`:

```python
_WRONG_RESULT = """## BUG DE RESULTADO ERRADO

Em `metadata.failure_mode`, diga como o bug aparece: `excecao` quando a função quebra
(exceção levantada ou assert falso), `resultado_errado` quando ela termina normalmente mas
devolve um valor errado ou deixa `self` num estado errado, e `outro` quando a falha depende
do ambiente. Um achado `resultado_errado` vai ao ESBMC mesmo com `verifiable` false: uma
etapa seguinte escreve a propriedade que o resultado correto cumpre.
"""


def _wrong_result(prompt: str) -> str:
    prompt = _swap("A15", prompt, "## SAÍDA: JSON válido", _WRONG_RESULT + "\n## SAÍDA: JSON válido")
    return _swap("A15", prompt, '"context_needed": ["<helper/import/classe necessária, se houver>"]',
                 '"context_needed": ["<helper/import/classe necessária, se houver>"],\n'
                 '        "failure_mode": "excecao | resultado_errado | outro"')
```

e em `VARIANTS` acrescentar `"A15": _wrong_result` depois de `"A12": _repo_callers`.

`src/research_pipeline/llm/schema.py`, em `v2_findings_schema`, antes de `if "A7" in variants:`:

```python
    if "A15" in variants:
        metadata = body["properties"]["findings"]["items"]["properties"]["metadata"]
        metadata["properties"]["failure_mode"] = {"type": "string",
                                                  "enum": ["excecao", "resultado_errado", "outro"]}
        metadata["required"].append("failure_mode")
```

e a docstring passa a citar `A15: failure_mode`.

`src/research_pipeline/llm/findings.py`, no dicionário `metadata` de `finding_from_dict`, depois da linha de `crash_expression`:

```python
            "failure_mode": str(metadata_raw.get("failure_mode", "")),
```

`src/main.py`: o import passa a ser `from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis`. No laço `for finding in findings:` de `mode_v2` (hoje `main.py:1369-1390`), trocar o começo do laço e a criação do candidato por:

```python
            for finding in findings:
                # With A15 the LLM says how the bug shows; a wrong result goes to the value oracle.
                wrong_result = "A15" in variants and finding.metadata.get("failure_mode") == "resultado_errado"
                # Otherwise the LLM decides: only findings it marks formally verifiable reach ESBMC.
                if not finding.verifiable and not wrong_result:
                    unit_rejections.append(
                        {
                            "file": str(file_path),
                            "function": unit.qualname,
                            "finding_type": finding.finding_type,
                            "expression": str(finding.metadata.get("expression", "")),
                            "violated_property": str(finding.metadata.get("violated_property", "")),
                        }
                    )
                    continue
                unit_candidates.append(
                    Candidate(
                        file=str(file_path),
                        function=unit.qualname,
                        expression=str(finding.metadata.get("expression", "")),
                        note=finding.explanation,
                        violated_property=str(finding.metadata.get("violated_property", "")),
                        oracle=VALUE_ORACLE if wrong_result else "",
                    )
                )
```

`_mode_v2_verify` já converte com `BugHypothesis.from_candidate`, que agora leva o oráculo.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_entry.py tests/test_prompt_variants.py tests/test_main_v2.py -q`
Expected: todos passam (7 novos).

- [ ] **Passo 5: suíte**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

- [ ] **Ponto de parada (sem commit).**

---

### Tarefa 2: linguagem da propriedade na spec

**Files:**
- Modify: `src/research_pipeline/verify/spec.py`
- Test: `tests/test_verify_value_spec.py` (novo)

**Interfaces:**
- Consumes: `VALUE_ORACLE` (Tarefa 1).
- Produces: `RESULT = "result"`; `InputSpec.returns: str = ""` e `InputSpec.postcondition: str = ""`; `parse_spec` lê as duas chaves; `spec_problems(spec: InputSpec, grounded: Grounded, *, require_property: bool = False) -> list[str]`; `ignored_keys` registra `returns`/`postcondition` de hipótese de exceção; `shape_unpacked` preserva as chaves novas.

- [ ] **Passo 1: testes que falham**

```python
import pytest

from research_pipeline.verify.grounding import Grounded, Param
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.spec import InputSpec, ignored_keys, parse_spec, shape_unpacked, spec_problems


def _grounded(oracle=VALUE_ORACLE, receiver=False, params=("x", "xs")):
    return Grounded(
        hypothesis=BugHypothesis("x.py", "C.m" if receiver else "f", "x + 1", oracle=oracle),
        class_name="C" if receiver else None,
        method_name="m" if receiver else "f",
        spans=((2, 2),),
        params=tuple(Param(name, "int" if name == "x" else "list[int]") for name in params),
        receiver_attrs=("total",) if receiver else (),
        module="",
        attr_annotations={"total": "int"} if receiver else {},
        entry="method" if receiver else "function",
    )


def _spec(postcondition, returns="int"):
    return InputSpec({}, {}, (), returns=returns, postcondition=postcondition)


def test_parse_spec_reads_returns_and_postcondition():
    spec = parse_spec('{"params": {}, "returns": "int", "postcondition": "result >= 0"}')
    assert (spec.returns, spec.postcondition) == ("int", "result >= 0")
    assert parse_spec('{"params": {}}').postcondition == ""


def test_parse_spec_rejects_a_postcondition_that_is_not_a_string():
    with pytest.raises(ValueError):
        parse_spec('{"postcondition": ["result > 0"]}')


@pytest.mark.parametrize(("postcondition", "ok"), [
    ("result >= 0", True),
    ("len(result) <= len(xs)", True),
    ("isinstance(result, int)", True),
    ("result in ('a', 'b')", True),
    ("result is None or result > x", True),
    ("not (result == x + 1)", True),
    ("x > 0", False),
    ("result.strip() == ''", False),
    ("sorted(xs) == result", False),
    ("result[0] == 1", False),
    ("isinstance(result, Foo)", False),
    ("result > y", False),
    ("result in (x, 1)", False),
    ("result >", False),
])
def test_postcondition_language(postcondition, ok):
    problems = spec_problems(_spec(postcondition), _grounded(), require_property=True)
    assert (problems == []) is ok, problems


def test_receiver_attributes_are_the_state_after_the_call():
    grounded = _grounded(receiver=True)
    assert spec_problems(_spec("self.total >= 0", returns="None"), grounded, require_property=True) == []
    assert spec_problems(_spec("self.other >= 0", returns="None"), grounded, require_property=True) != []


def test_result_cannot_be_read_when_nothing_is_returned():
    problems = spec_problems(_spec("result >= 0", returns="None"), _grounded(), require_property=True)
    assert any("returns is None" in p for p in problems)


def test_value_hypotheses_need_both_fields_only_when_asked():
    assert spec_problems(InputSpec({}, {}, ()), _grounded()) == []
    problems = spec_problems(InputSpec({}, {}, ()), _grounded(), require_property=True)
    assert "returns: missing type" in problems and "postcondition: missing" in problems


def test_object_is_not_a_return_type():
    problems = spec_problems(_spec("result is not None", returns="object"), _grounded(), require_property=True)
    assert any(p.startswith("returns:") for p in problems)


def test_a_parameter_named_result_is_reported():
    problems = spec_problems(_spec("result >= 0"), _grounded(params=("x", "result")), require_property=True)
    assert any("named result" in p for p in problems)


def test_exception_hypotheses_ignore_the_value_fields():
    grounded = _grounded(oracle="")
    assert ignored_keys(_spec("x > 0"), grounded) == ["returns", "postcondition"]
    assert spec_problems(_spec("x > 0"), grounded) == []


def test_shape_unpacked_keeps_the_value_fields():
    spec = shape_unpacked(_spec("result >= 0"), _grounded())
    assert (spec.returns, spec.postcondition) == ("int", "result >= 0")
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_spec.py -q`
Expected: falhas com `TypeError: InputSpec.__init__() got an unexpected keyword argument 'returns'`.

- [ ] **Passo 3: implementação**

Em `src/research_pipeline/verify/spec.py`: imports passam a incluir `from dataclasses import dataclass, field, replace` e `from .hypothesis import VALUE_ORACLE`. Em `InputSpec`, depois de `stubs`:

```python
    # Wrong-result hypotheses only: the returned type and the property every correct call satisfies.
    returns: str = ""
    postcondition: str = ""
```

`parse_spec` passa a terminar assim:

```python
    returns, postcondition = data.get("returns") or "", data.get("postcondition") or ""
    if not (isinstance(returns, str) and isinstance(postcondition, str)):
        raise ValueError("returns and postcondition must be strings")
    return InputSpec(
        {str(k): str(v) for k, v in params.items()},
        {str(k): str(v) for k, v in attributes.items()},
        tuple(str(a) for a in assumptions),
        {str(k): str(v) for k, v in stubs.items()},
        returns,
        postcondition,
    )
```

Depois de `_assumption_problem`:

```python
RESULT = "result"
_TYPE_NAMES = frozenset({*SCALARS, "bytes", "list", "dict", "tuple", "set", "frozenset"})


def _postcondition_problem(text: str, params: set[str], attrs: set[str], receiver: bool) -> str:
    """An assumption's language plus ``result`` and ``isinstance(x, T)``. It must read ``result`` or a
    receiver attribute: a property of the inputs alone says nothing about what the call did."""
    if RESULT in params:
        return "postcondition: a parameter is named result, which the postcondition reserves for the return value"
    try:
        tree = ast.parse(text.strip(), mode="eval")
    except SyntaxError:
        return f"postcondition {text!r} is not a Python expression"
    type_names: set[int] = set()
    for node in ast.walk(tree):
        if not isinstance(node, _ALLOWED_NODES):
            return f"postcondition {text!r} uses {type(node).__name__}"
        if isinstance(node, ast.Call):
            name = node.func.id if isinstance(node.func, ast.Name) else ""
            if name == "len" and len(node.args) == 1:
                continue
            if (name == "isinstance" and len(node.args) == 2 and isinstance(node.args[1], ast.Name)
                    and node.args[1].id in _TYPE_NAMES):
                type_names.add(id(node.args[1]))
                continue
            return f"postcondition {text!r} may only call len() and isinstance(x, <builtin type>)"
        if isinstance(node, ast.Tuple) and not all(isinstance(e, ast.Constant) for e in node.elts):
            return f"postcondition {text!r} may only use a tuple of constants"
        if isinstance(node, ast.Attribute) and not (
                receiver and isinstance(node.value, ast.Name) and node.value.id == "self" and node.attr in attrs):
            return f"postcondition {text!r} reads an attribute that is not a receiver attribute"
    names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name) and id(n) not in type_names}
    names -= {"len", "isinstance", "self"} if receiver else {"len", "isinstance"}
    unknown = names - params - {RESULT}
    if unknown:
        return f"postcondition {text!r} uses unknown name(s) {', '.join(sorted(unknown))}"
    if RESULT not in names and not any(isinstance(n, ast.Attribute) for n in ast.walk(tree)):
        return f"postcondition {text!r} reads neither result nor a receiver attribute"
    return ""


def _value_problems(spec: InputSpec, params: set[str], attrs: set[str], receiver: bool) -> list[str]:
    problems = []
    shape = parse_type(spec.returns) if spec.returns else None
    if not spec.returns:
        problems.append("returns: missing type")
    elif shape is None or shape.kind == OBJECT:
        problems.append(f"returns: {spec.returns!r} is not an allowed return type (object is not allowed)")
    if not spec.postcondition:
        return [*problems, "postcondition: missing"]
    problem = _postcondition_problem(spec.postcondition, params, attrs, receiver)
    if problem:
        return [*problems, problem]
    read = {n.id for n in ast.walk(ast.parse(spec.postcondition.strip(), mode="eval")) if isinstance(n, ast.Name)}
    if shape is not None and shape.kind == "none" and RESULT in read:
        problems.append("postcondition reads result, but returns is None: read self.<attribute> instead")
    return problems
```

`ignored_keys` passa a ser:

```python
def ignored_keys(spec: InputSpec, grounded: Grounded) -> list[str]:
    """Names the spec gives that the harness has no use for. They change nothing in the program,
    so they are recorded, not rejected: a rejection would spend an LLM call on a harmless extra."""
    params, attributes = resolved_types(spec, grounded)
    stubs = {*grounded.stub_keys, *_object_keys(spec, grounded)}
    value_keys = [] if grounded.hypothesis.oracle == VALUE_ORACLE else [
        key for key, text in (("returns", spec.returns), ("postcondition", spec.postcondition)) if text]
    return ([f"param {n}" for n in spec.params if n not in params]
            + [f"attribute {n}" for n in spec.attributes if n not in attributes]
            + [f"stub {k}" for k in spec.stubs if k not in stubs]
            + value_keys)
```

Última linha de `shape_unpacked`:

```python
    return replace(spec, params=params, attributes=attributes, stubs=stubs)
```

`spec_problems` ganha o parâmetro e o bloco final:

```python
def spec_problems(spec: InputSpec, grounded: Grounded, *, require_property: bool = False) -> list[str]:
    """``require_property``: a wrong-result hypothesis must give ``returns`` and ``postcondition``. Without
    it they are checked only when given, so the precheck's placeholder spec renders."""
```

e, antes do `return problems`:

```python
    if grounded.hypothesis.oracle == VALUE_ORACLE and (require_property or spec.returns or spec.postcondition):
        problems += _value_problems(spec, set(params), set(attributes), grounded.has_receiver)
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_spec.py tests/test_verify_spec.py -q`
Expected: todos passam (23 novos).

- [ ] **Passo 5: suíte**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

- [ ] **Ponto de parada (sem commit).**

---

### Tarefa 3: `assert` da propriedade no harness

**Files:**
- Modify: `src/research_pipeline/verify/render.py`
- Test: `tests/test_verify_value_render.py` (novo)

**Interfaces:**
- Consumes: `VALUE_ORACLE` (Tarefa 1); `RESULT`, `InputSpec.returns`, `InputSpec.postcondition` (Tarefa 2).
- Produces: `RESULT_VAR = "_esbmc_result"`; `Program.property_line: int = 0` (linha do `assert` em `source`, a cópia do ESBMC) e `Program.replay_property_line: int | None = None` (linha em `replay_source`; `None` quer dizer a mesma, como `replay_target_spans`); `_driver(grounded, params, assumptions, decl, returns: str = "", postcondition: str = "") -> list[str]`; `RenderError` para construtor com oráculo de valor.

As duas linhas podem diferir: `split_conditional_assignments` (`compat.py`, chamado em `render_program`) acrescenta linhas só na cópia do ESBMC e então recalcula `driver_start` para ela.

- [ ] **Passo 1: testes que falham**

```python
from dataclasses import replace

import pytest

from research_pipeline.verify.grounding import Grounded, ground
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.render import RenderError, render_program
from research_pipeline.verify.spec import InputSpec

MAGNITUDE = "def magnitude(x):\n    return x if x > 0 else x\n"
ACCOUNT = '''class Account:
    def __init__(self):
        self.balance = 0

    def deposit(self, amount):
        self.balance = self.balance - amount
'''
SCALED = "def scaled(x):\n    y = x * 2\n    return y + 1\n"
# split_conditional_assignments turns line 2 into two lines in the ESBMC copy only.
PICK = "def pick(c, x):\n    f = x if c else (lambda v: -v)\n    return x + 1\n"


def _ground(source, function, expression, oracle=VALUE_ORACLE):
    grounded = ground(BugHypothesis("m.py", function, expression, oracle=oracle), source)
    assert isinstance(grounded, Grounded)
    return grounded


def test_value_driver_asserts_the_postcondition_on_the_returned_value():
    spec = InputSpec({"x": "int"}, {}, (), returns="int", postcondition="result >= 0")
    program = render_program(_ground(MAGNITUDE, "magnitude", "x if x > 0 else x"), spec)
    assert "    _esbmc_result: int = magnitude(x)\n    assert _esbmc_result >= 0\n" in program.source
    assert program.source.splitlines()[program.property_line - 1] == "    assert _esbmc_result >= 0"
    assert program.replay_source.splitlines()[program.replay_property_line - 1] == "    assert _esbmc_result >= 0"


def test_the_property_line_follows_each_copy_when_only_the_esbmc_copy_grows():
    spec = InputSpec({"c": "bool", "x": "int"}, {}, (), returns="int", postcondition="result > x")
    program = render_program(_ground(PICK, "pick", "x + 1"), spec)
    assert any(t.startswith("conditional_assignments_split") for t in program.transforms)
    assert program.property_line == program.replay_property_line + 1
    assert program.source.splitlines()[program.property_line - 1] == "    assert _esbmc_result > x"
    assert program.replay_source.splitlines()[program.replay_property_line - 1] == "    assert _esbmc_result > x"


def test_a_method_postcondition_reads_the_receiver_after_the_call():
    spec = InputSpec({"amount": "int"}, {"balance": "int"}, (), returns="None",
                     postcondition="self.balance >= 0 or amount < 0")
    program = render_program(_ground(ACCOUNT, "Account.deposit", "self.balance - amount"), spec)
    assert "    _receiver.deposit(amount)\n    assert _receiver.balance >= 0 or amount < 0\n" in program.source
    assert "_esbmc_result" not in program.source


def test_value_hypotheses_keep_the_code_after_the_suspect():
    exception = render_program(_ground(SCALED, "scaled", "x * 2", oracle=""), InputSpec({"x": "int"}, {}, ()))
    assert any(t.startswith("cut_after_suspect") for t in exception.transforms)
    assert exception.property_line == 0
    value = render_program(_ground(SCALED, "scaled", "x * 2"),
                           InputSpec({"x": "int"}, {}, (), returns="int", postcondition="result > x"))
    assert "    return y + 1" in value.source
    assert not any(t.startswith("cut_after_suspect") for t in value.transforms)


def test_a_constructor_cannot_carry_a_value_oracle():
    grounded = replace(_ground(MAGNITUDE, "magnitude", "x if x > 0 else x"), entry="constructor")
    with pytest.raises(RenderError, match="constructor"):
        render_program(grounded, InputSpec({"x": "int"}, {}, ()))
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_render.py -q`
Expected: 5 falhas (sem `assert` no driver, `property_line` inexistente, corte aplicado, construtor aceito).

- [ ] **Passo 3: implementação**

Imports de `render.py`: `from .hypothesis import VALUE_ORACLE` e `RESULT` na lista de `from .spec import (...)`. Depois de `DRIVER = "_esbmc_main"`:

```python
RESULT_VAR = "_esbmc_result"
```

Em `Program`, dois campos no fim:

```python
    property_line: int = 0  # the driver's assert of a wrong-result hypothesis, in ``source``
    replay_property_line: int | None = None  # the same assert in ``replay_source``; None: same line
```

Depois de `_ToReceiver`:

```python
class _ToResult(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.Name:
        return ast.copy_location(ast.Name(RESULT_VAR, node.ctx), node) if node.id == RESULT else node
```

`_driver` inteiro passa a ser:

```python
def _driver(grounded: Grounded, params: dict[str, str], assumptions: tuple[str, ...], decl: _Declarer,
            returns: str = "", postcondition: str = "") -> list[str]:
    """With ``postcondition``, the call's value goes to RESULT_VAR (unless ``returns`` is None) and the
    postcondition's ``assert`` is the driver's last line."""
    lines = [f"def {DRIVER}() -> None:"]
    for name, type_text in params.items():
        lines += decl.declare(name, type_text, "    ", object_class(name))
    receiver = grounded.has_receiver
    if receiver:
        receiver_class = RECEIVER_CLASS if grounded.receiver_subclass else grounded.class_name
        lines.append(f"    {RECEIVER} = {receiver_class}()")
    for assumption in assumptions:
        tree = _ToReceiver().visit(ast.parse(assumption.strip(), mode="eval"))
        lines.append(f"    __ESBMC_assume({ast.unparse(tree)})")
    keyword = {p.name for p in grounded.params if p.keyword}
    args = ", ".join(f"{name}={name}" if name in keyword else name for name in params)
    if receiver:
        call = f"{RECEIVER}.{grounded.method_name}({args})"
    elif grounded.entry == "constructor":
        call = f"{grounded.class_name}({args})"
    elif grounded.class_name:
        call = f"{grounded.class_name}.{grounded.method_name}({args})"
    else:
        call = f"{grounded.method_name}({args})"
    if not postcondition:
        return [*lines, f"    {call}"]
    shape = parse_type(returns)
    if shape is None or shape.kind == "none":
        lines.append(f"    {call}")
    else:
        lines.append(f"    {RESULT_VAR}: {_annotation(shape)} = {call}")
    tree = _ToResult().visit(_ToReceiver().visit(ast.parse(postcondition.strip(), mode="eval")))
    return [*lines, f"    assert {ast.unparse(tree)}"]
```

Em `render_program`, depois do bloco `if problems: raise RenderError(...)`:

```python
    value = grounded.hypothesis.oracle == VALUE_ORACLE
    if value and grounded.entry == "constructor":
        raise RenderError("the value oracle needs a returned value or a receiver; a constructor call has neither")
```

A linha `driver = _driver(grounded, params, spec.assumptions, decl)` passa a ser:

```python
    driver = _driver(grounded, params, spec.assumptions, decl,
                     spec.returns if value else "", spec.postcondition if value else "")
```

A linha `rewritten, cut = cut_after_suspect(rewritten, target, rewritten_spans)` passa a ser:

```python
    # A wrong value shows only after the function returns: its path must not end at the suspect.
    rewritten, cut = (rewritten, []) if value else cut_after_suspect(rewritten, target, rewritten_spans)
```

Logo antes de `rewritten_range = target_range` (o `driver_start` ali já inclui o deslocamento das guardas e ainda vale para as duas cópias):

```python
    # The assert is the driver's last line; the split below may move it in the ESBMC copy only.
    replay_property_line = driver_start + len(driver) - 1 if value and spec.postcondition else 0
```

Depois do bloco `if split:` (que recalcula `driver_start` para a cópia do ESBMC):

```python
    property_line = driver_start + len(driver) - 1 if replay_property_line else 0
```

E o `return Program(...)` ganha `property_line=property_line, replay_property_line=replay_property_line` como últimos argumentos.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_render.py tests/test_verify_render.py -q`
Expected: todos passam (5 novos).

- [ ] **Passo 5: suíte**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

- [ ] **Ponto de parada (sem commit).**

---

### Tarefa 4: replay reconhece a violação da propriedade

**Files:**
- Modify: `src/research_pipeline/verify/replay_worker.py`
- Modify: `src/research_pipeline/verify/replay.py`
- Test: `tests/test_verify_value_replay.py` (novo)

**Interfaces:**
- Consumes: `Program.property_line` (Tarefa 3).
- Produces: status `"property_violated"` em `ReplayVerdict` (com `line` igual à linha da propriedade no programa replayado, `exception_type == "AssertionError"`, `inputs`); config do worker com `"property_line"`; no modo propriedade, entrada fixa descartada dá `"unavailable"`. Assinatura de `concrete_replay` inalterada: ela lê `program.replay_property_line`, ou `program.property_line` quando o primeiro é `None` (mesma regra de `replay_target_spans`).

- [ ] **Passo 1: testes que falham**

```python
from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import concrete_replay

VALUE = '''def magnitude(x):
    return x if x > 0 else x


def _esbmc_main() -> None:
    x: int = nondet_int()
    _esbmc_result: int = magnitude(x)
    assert _esbmc_result >= 0


_esbmc_main()
'''
ASSERT = "    assert _esbmc_result >= 0"


def _program(source, spans=((2, 2),), with_property=True):
    lines = source.splitlines()
    end = lines.index("def _esbmc_main() -> None:") - 2
    return Program(source, lines.index("def _esbmc_main() -> None:") + 1, spans, (), (1, end),
                   property_line=lines.index(ASSERT) + 1 if with_property else 0)


def test_the_search_finds_an_input_that_violates_the_property():
    program = _program(VALUE)
    verdict = concrete_replay(program, "magnitude")
    assert (verdict.status, verdict.line, verdict.inputs) == ("property_violated", program.property_line, [-1])
    assert verdict.exception_type == "AssertionError"


def test_the_fixed_function_keeps_the_property():
    fixed = VALUE.replace("else x\n", "else -x\n")
    assert concrete_replay(_program(fixed), "magnitude").status == "not_reproduced"


def test_fixed_inputs_run_once():
    assert concrete_replay(_program(VALUE), "magnitude", inputs=[-1]).status == "property_violated"
    assert concrete_replay(_program(VALUE), "magnitude", inputs=[2]).status == "not_reproduced"


def test_an_assert_inside_the_target_is_not_the_property():
    inner = VALUE.replace("    return x if x > 0 else x", "    assert x >= 0\n    return x if x > 0 else x")
    verdict = concrete_replay(_program(inner, spans=((3, 3),)), "magnitude")
    assert verdict.status == "other_failure" and verdict.line == 2


def test_without_a_property_line_a_driver_assert_stays_other_failure():
    assert concrete_replay(_program(VALUE, with_property=False), "magnitude").status == "other_failure"


def test_a_discarded_fixed_run_is_unavailable_with_a_property():
    assumed = VALUE.replace("    x: int = nondet_int()\n", "    x: int = nondet_int()\n    __ESBMC_assume(x != -1)\n")
    assert concrete_replay(_program(assumed), "magnitude", inputs=[-1]).status == "unavailable"
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_replay.py -q`
Expected: falham os testes 1, 3 e 6 (status `other_failure`/`not_reproduced` em vez de `property_violated`/`unavailable`); 2, 4 e 5 já passam (protegem o comportamento atual).

- [ ] **Passo 3: implementação**

`replay_worker.py`, `_run_once` inteiro:

```python
def _run_once(code, chooser, domains, max_list, target):
    """One execution: None when it ended normally, _DISCARDED when an assume or the per-run timer
    cut it, else the crash record. With a property line, the driver's AssertionError raised there is a
    property violation; any other exception follows the usual rules."""
    function, spans, first, last, property_line = target
    real_stdout = sys.stdout
    sys.stdout = io.StringIO()
    signal.setitimer(signal.ITIMER_REAL, RUN_SECONDS)
    try:
        exec(code, {"__name__": "__main__", **_intrinsics(chooser, domains, max_list)})  # noqa: S102 - the replay is the point; host_replay_problem gates it
    except _Discard:
        return _DISCARDED
    except Exception as exc:  # noqa: BLE001 - every crash is evidence
        frames = [f for f in traceback.extract_tb(exc.__traceback__) if f.filename == "<program>"]
        if (property_line and isinstance(exc, AssertionError) and frames
                and frames[-1].name == "_esbmc_main" and frames[-1].lineno == property_line):
            return {"status": "property_violated", "exception_type": "AssertionError", "line": property_line,
                    "inputs": chooser.values, "message": str(exc)[:300], "raised_at": property_line}
        # Name and line range together: another class's method may share the name.
        in_target = [f for f in frames if f.name == function and (not last or first <= f.lineno <= last)]
        line = in_target[-1].lineno if in_target else (frames[-1].lineno if frames else None)
        reproduced = bool(in_target) and any(start <= line <= end for start, end in spans)
        return {"status": "reproduced" if reproduced else "other_failure",
                "exception_type": type(exc).__name__, "line": line, "inputs": chooser.values,
                "message": str(exc)[:300], "raised_at": frames[-1].lineno if frames else None}
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        sys.stdout = real_stdout
    return None
```

Em `_fixed`, antes do `return outcome if isinstance(...)`:

```python
    if outcome == _DISCARDED and target[4]:
        # With a property, a cut run would read as "the property held".
        return {"status": "unavailable", "reason": "the run was discarded (a failed assumption or the time limit)",
                "inputs": inputs}
```

Em `main`, a linha `target = ...` e a condição de parada da busca:

```python
    target = (config["function"], config["spans"], first, last, config.get("property_line", 0))
    # A wrong-result hypothesis looks for its property's violation, not for an exception at the suspect.
    wanted = "property_violated" if target[4] else "reproduced"
```

e, no laço, `if outcome["status"] == "reproduced":` passa a ser `if outcome["status"] == wanted:`.

`replay.py`: comentário do status vira `# reproduced | property_violated | other_failure | not_reproduced | unavailable`. Em `concrete_replay`, junto das linhas que escolhem `spans` e `target_range`:

```python
    property_line = program.property_line if program.replay_property_line is None else program.replay_property_line
```

o dicionário `config` ganha `"property_line": property_line`; e, depois do bloco que desconfia de `reproduced` fora do alvo:

```python
    if data.get("status") == "property_violated" and line != property_line:
        return ReplayVerdict("unavailable", reason=f"replay reported a property violation at line {line}, "
                                                   "not at the property")
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_replay.py tests/test_verify_replay.py tests/test_verify_replay_pinned.py tests/test_verify_replay_random.py -q`
Expected: todos passam (6 novos).

- [ ] **Passo 5: suíte**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

- [ ] **Ponto de parada (sem commit).**

---

### Tarefa 5: vereditos de valor e controle com a versão corrigida

**Files:**
- Modify: `src/research_pipeline/verify/outcome.py`
- Create: `src/research_pipeline/verify/value_oracle.py`
- Test: `tests/test_verify_value_oracle.py` (novo)

**Interfaces:**
- Consumes: `Program.property_line` (Tarefa 3); status `property_violated` (Tarefa 4).
- Produces: em `outcome.py`, `VALUE_VIOLATION`, `VALUE_CONFIRMED`, `PROPERTY_REJECTED` (em `VERDICTS` e `CHECKED`). Em `value_oracle.py`: `esbmc_hits_property(esbmc: ESBMCDirectResult, property_line: int) -> bool`; `value_verdict(reading: EsbmcReading, property_hit: bool, replay: ReplayVerdict) -> str`; `control_program(program: Program, function: str, fixed_source: str) -> Program | None`; `check_fixed(program: Program, function: str, method_name: str, fixed_source: str, inputs: list | None) -> ReplayVerdict`; `apply_control(verdict: str, control: ReplayVerdict | None) -> tuple[str, str]`.

- [ ] **Passo 1: testes que falham**

```python
from dataclasses import replace

import pytest

from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify.outcome import (
    CHECKED,
    ESBMC_MISSED,
    ESBMC_TIMEOUT,
    NOT_CONFIRMED,
    OTHER_FAILURE,
    PROPERTY_REJECTED,
    UNVALIDATED,
    VALUE_CONFIRMED,
    VALUE_VIOLATION,
    VERDICTS,
    EsbmcReading,
)
from research_pipeline.verify.render import Program
from research_pipeline.verify.replay import ReplayVerdict, concrete_replay
from research_pipeline.verify.value_oracle import (
    apply_control,
    check_fixed,
    control_program,
    esbmc_hits_property,
    value_verdict,
)

VALUE = '''def magnitude(x):
    return x if x > 0 else x


def _esbmc_main() -> None:
    x: int = nondet_int()
    _esbmc_result: int = magnitude(x)
    assert _esbmc_result >= 0


_esbmc_main()
'''
FIXED = "def magnitude(x):\n    # the fix\n    return x if x > 0 else -x\n"
PROPERTY_LINE = 8


def _program():
    return Program(VALUE, 5, ((2, 2),), (), (1, 2), property_line=PROPERTY_LINE)


VIOLATION, SAFE, TIMEOUT = EsbmcReading("violation", "assertion"), EsbmcReading("safe", ""), EsbmcReading("timeout", "")


@pytest.mark.parametrize(("reading", "hit", "status", "expected"), [
    (VIOLATION, True, "property_violated", VALUE_VIOLATION),
    (VIOLATION, False, "property_violated", UNVALIDATED),
    (VIOLATION, True, "other_failure", OTHER_FAILURE),
    (VIOLATION, True, "reproduced", OTHER_FAILURE),
    (VIOLATION, True, "not_reproduced", UNVALIDATED),
    (SAFE, False, "property_violated", ESBMC_MISSED),
    (SAFE, False, "not_reproduced", NOT_CONFIRMED),
    (TIMEOUT, False, "unavailable", ESBMC_TIMEOUT),
])
def test_value_verdict(reading, hit, status, expected):
    assert value_verdict(reading, hit, ReplayVerdict(status)) == expected


@pytest.mark.parametrize(("verdict", "control", "expected"), [
    (VALUE_VIOLATION, ReplayVerdict("property_violated"), PROPERTY_REJECTED),
    (VALUE_VIOLATION, ReplayVerdict("not_reproduced"), VALUE_CONFIRMED),
    (VALUE_VIOLATION, ReplayVerdict("reproduced", "ValueError"), VALUE_VIOLATION),
    (VALUE_VIOLATION, ReplayVerdict("unavailable", reason="discarded"), VALUE_VIOLATION),
    (VALUE_VIOLATION, None, VALUE_VIOLATION),
    (NOT_CONFIRMED, ReplayVerdict("not_reproduced"), NOT_CONFIRMED),
])
def test_control_needs_a_clean_run_of_the_fixed_version(verdict, control, expected):
    assert apply_control(verdict, control)[0] == expected


def _esbmc(records):
    return ESBMCDirectResult(source_file="p.py", status="violation_found", command=["esbmc"], returncode=1,
                             summary="", details={"violated_property_records": records})


def test_esbmc_hits_only_the_assert_at_the_property_line():
    assert esbmc_hits_property(_esbmc([{"kind": "assertion", "line": 8}]), 8)
    assert not esbmc_hits_property(_esbmc([{"kind": "assertion", "line": 2}]), 8)
    assert not esbmc_hits_property(_esbmc([{"kind": "division by zero", "line": 8}]), 8)
    assert not esbmc_hits_property(_esbmc([{"kind": "unwinding assertion loop 1", "line": 8}]), 8)
    assert not esbmc_hits_property(_esbmc([]), 8)


def test_the_fixed_function_replaces_the_target_and_moves_the_property_line():
    control = control_program(_program(), "magnitude", FIXED)
    assert control.property_line == PROPERTY_LINE + 1
    assert control.source.splitlines()[control.property_line - 1] == "    assert _esbmc_result >= 0"
    assert "else -x" in control.source and "else x\n" not in control.source
    assert concrete_replay(control, "magnitude", inputs=[-1]).status == "not_reproduced"
    # The swap works on the replay copy, so it starts from the replay's property line.
    grown = replace(_program(), property_line=PROPERTY_LINE + 2, replay_property_line=PROPERTY_LINE)
    assert control_program(grown, "magnitude", FIXED).property_line == PROPERTY_LINE + 1


def test_a_fixed_file_without_the_function_gives_no_control():
    assert control_program(_program(), "magnitude", "def other():\n    pass\n") is None
    assert check_fixed(_program(), "magnitude", "magnitude", "def other():\n    pass\n", [-1]).status == "unavailable"


def test_no_inputs_means_no_control():
    assert check_fixed(_program(), "magnitude", "magnitude", FIXED, None).status == "unavailable"


def test_new_verdict_names_do_not_collide():
    existing = {"CONFIRMED", "ESBMC_MISSED", "UNVALIDATED", "OTHER_FAILURE", "NOT_CONFIRMED", "GROUNDING_FAILED",
                "MISSING_DEPENDENCY", "UNSUPPORTED", "SPEC_FAILED", "ESBMC_TIMEOUT", "ESBMC_ERROR",
                "PIPELINE_ERROR", "NO_SOURCE", "AGENT_FAILED", "CONFIRMED_SIMPLIFIED", "STUB_INDUCED",
                "FIXED_ALSO_FAILS", "FUZZ_FOUND", "FUZZ_OTHER", "FUZZ_NOTHING", "FUZZ_UNAVAILABLE", "PINNED_SAFE",
                "PINNED_UNAVAILABLE", "LLM_INPUT_NOTHING", "LLM_INPUT_UNAVAILABLE", "ARM_FAILED", "TARGET_ALTERED"}
    new = {VALUE_VIOLATION, VALUE_CONFIRMED, PROPERTY_REJECTED}
    assert len(new) == 3 and new.isdisjoint(existing)
    assert new <= set(VERDICTS) and new <= CHECKED
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_oracle.py -q`
Expected: erro na coleta, `ImportError: cannot import name 'PROPERTY_REJECTED'`.

- [ ] **Passo 3: implementação**

`outcome.py`, depois de `NO_SOURCE = "NO_SOURCE"`:

```python
# Wrong-result hypotheses (verify/value_oracle.py): ESBMC and the replay agree the original breaks the
# postcondition; the fixed version then keeps it (confirmed), also breaks it (property rejected), or
# could not tell (violation only).
VALUE_VIOLATION = "VALUE_VIOLATION"
VALUE_CONFIRMED = "VALUE_CONFIRMED"
PROPERTY_REJECTED = "PROPERTY_REJECTED"
```

e as duas constantes seguintes passam a ser:

```python
VERDICTS = (CONFIRMED, ESBMC_MISSED, UNVALIDATED, OTHER_FAILURE, NOT_CONFIRMED, GROUNDING_FAILED,
            MISSING_DEPENDENCY, UNSUPPORTED, SPEC_FAILED, ESBMC_TIMEOUT, ESBMC_ERROR, PIPELINE_ERROR, NO_SOURCE,
            VALUE_CONFIRMED, VALUE_VIOLATION, PROPERTY_REJECTED)
# Verdicts reached by a program ESBMC actually checked: the success@k numerator.
CHECKED = frozenset({CONFIRMED, ESBMC_MISSED, UNVALIDATED, OTHER_FAILURE, NOT_CONFIRMED,
                     VALUE_CONFIRMED, VALUE_VIOLATION, PROPERTY_REJECTED})
```

`value_oracle.py` (novo):

```python
"""Wrong-result hypotheses: ESBMC looks for an input that breaks the LLM's postcondition, the CPython
replay confirms the original breaks it, and (evaluation only) the fixed version, fed the same input,
must keep it. The fixed version is read only here, after the LLM is done."""

from __future__ import annotations

import ast
import textwrap

from research_pipeline.models import ESBMCDirectResult

from .astutil import find_function
from .outcome import (
    ESBMC_MISSED,
    NOT_CONFIRMED,
    OTHER_FAILURE,
    PROPERTY_REJECTED,
    UNVALIDATED,
    VALUE_CONFIRMED,
    VALUE_VIOLATION,
    EsbmcReading,
    final_verdict,
)
from .render import Program
from .replay import ReplayVerdict, concrete_replay


def esbmc_hits_property(esbmc: ESBMCDirectResult, property_line: int) -> bool:
    """By line, not by message: the text ESBMC prints for an assert is not part of the contract."""
    records = esbmc.details.get("violated_property_records") or []
    return any(str(r.get("kind", "")).lower().startswith("assertion") and r.get("line") == property_line
               for r in records)


def value_verdict(reading: EsbmcReading, property_hit: bool, replay: ReplayVerdict) -> str:
    if reading.kind == "violation":
        if replay.status == "property_violated":
            return VALUE_VIOLATION if property_hit else UNVALIDATED
        return OTHER_FAILURE if replay.status in {"reproduced", "other_failure"} else UNVALIDATED
    if reading.kind in {"safe", "artifact"}:
        return ESBMC_MISSED if replay.status == "property_violated" else NOT_CONFIRMED
    return final_verdict(reading, replay)


def _first_line(node: ast.FunctionDef) -> int:
    return min([node.lineno, *(d.lineno for d in node.decorator_list)])


def control_program(program: Program, function: str, fixed_source: str) -> Program | None:
    """The replay program with the target swapped for its fixed version; the property line moves by the
    difference in length (the driver follows the target). None when either function is missing or the
    swap does not parse. Only the target is swapped: helpers stay as in the buggy version."""
    source = program.replay_source or program.source
    try:
        target = find_function(ast.parse(source), function)
        fixed = find_function(ast.parse(fixed_source), function)
    except SyntaxError:
        return None
    if target is None or fixed is None:
        return None
    first = _first_line(target)
    text = "\n".join(fixed_source.splitlines()[_first_line(fixed) - 1:fixed.end_lineno])
    body = textwrap.indent(textwrap.dedent(text), " " * target.col_offset).splitlines()
    lines = source.splitlines()
    spliced = "\n".join([*lines[:first - 1], *body, *lines[target.end_lineno:]]) + "\n"
    try:
        swapped = find_function(ast.parse(spliced), function)
    except SyntaxError:
        return None
    if swapped is None:
        return None
    delta = len(body) - (target.end_lineno - first + 1)
    line = program.property_line if program.replay_property_line is None else program.replay_property_line
    span = (swapped.lineno, swapped.end_lineno)
    return Program(spliced, 0, (span,), (), span, property_line=line + delta)


def check_fixed(program: Program, function: str, method_name: str, fixed_source: str,
                inputs: list | None) -> ReplayVerdict:
    """One run of the fixed version with the input that broke the original."""
    if inputs is None:
        return ReplayVerdict("unavailable", reason="the replay kept no input to give the fixed version")
    control = control_program(program, function, fixed_source)
    if control is None:
        return ReplayVerdict("unavailable", reason="the fixed function does not fit the replay program")
    return concrete_replay(control, method_name, inputs=inputs)


def apply_control(verdict: str, control: ReplayVerdict | None) -> tuple[str, str]:
    """Only a clean run of the fixed version (it ends and keeps the property) confirms; an exception or
    an unavailable run says nothing about the property."""
    if verdict != VALUE_VIOLATION or control is None:
        return verdict, ""
    if control.status == "property_violated":
        return PROPERTY_REJECTED, "the fixed version breaks the property with the same input"
    if control.status == "not_reproduced":
        return VALUE_CONFIRMED, ""
    detail = control.exception_type or control.reason
    return VALUE_VIOLATION, f"control inconclusive: {control.status} {detail}".strip()
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_oracle.py tests/test_verify_outcome.py tests/test_verify_report.py -q`
Expected: todos passam (19 novos).

- [ ] **Passo 5: suíte**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

- [ ] **Ponto de parada (sem commit).**

---

### Tarefa 6: o loop pede a propriedade, verifica e roda o controle

**Files:**
- Create: `src/research_pipeline/prompts/value_property_prompt.txt`
- Modify: `src/research_pipeline/verify/loop.py`
- Modify: `src/main.py`
- Test: `tests/test_verify_value_loop.py` (novo)

**Interfaces:**
- Consumes: tudo das Tarefas 1 a 5.
- Produces: `VALUE_PROMPT` em `loop.py`; `verify_hypothesis(..., fixed_source: str | None = None) -> VerifyResult`; `VerifyResult.control: dict` (em `to_dict` só quando não vazio); `run_verify(..., fixed_sources: Path | None = None, ...)`; argumento `--fixed-sources DIR` no `main.py`, repassado a `run_verify` e gravado em `config["fixed_sources"]`.

- [ ] **Passo 1: testes que falham**

```python
import json
from dataclasses import dataclass, field
from pathlib import Path

import main
from research_pipeline.models import ESBMCDirectResult
from research_pipeline.verify import esbmc_run, loop
from research_pipeline.verify.hypothesis import VALUE_ORACLE, BugHypothesis
from research_pipeline.verify.llm_client import SynthResult
from research_pipeline.verify.outcome import PROPERTY_REJECTED, VALUE_CONFIRMED, VALUE_VIOLATION

SOURCE = "def magnitude(x):\n    return x if x > 0 else x\n"
FIXED = "def magnitude(x):\n    # FIXED_ONLY_MARKER\n    return x if x > 0 else -x\n"
GOOD = json.dumps({"params": {"x": "int"}, "returns": "int", "postcondition": "result >= 0"})


@dataclass
class FakeLLM:
    replies: list[str]
    model: str = "fake"
    systems: list[str] = field(default_factory=list)
    prompts: list[str] = field(default_factory=list)

    def complete(self, system_prompt, user_prompt, *, json_mode=False):
        self.systems.append(system_prompt)
        self.prompts.append(user_prompt)
        return SynthResult(harness=self.replies.pop(0), raw_response="", model=self.model,
                           telemetry={"total_tokens": 10})


def _esbmc_hits_the_assert(path, **_):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    line = next((n for n, text in enumerate(lines, 1) if text.strip().startswith("assert ")), 0)
    return ESBMCDirectResult(source_file=str(path), status="violation_found", command=["esbmc"], returncode=1,
                             summary="violation_found",
                             details={"violated_properties": ["assertion"], "violated_files": [""],
                                      "violated_property_records": [{"kind": "assertion", "line": line}]})


def _run(work_dir, monkeypatch, llm, fixed=FIXED, oracle=VALUE_ORACLE):
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc_hits_the_assert)
    monkeypatch.setattr(loop, "convert", lambda source, command: "")
    h = BugHypothesis("m.py", "magnitude", "x if x > 0 else x", oracle=oracle)
    return loop.verify_hypothesis(h, llm=llm, source=SOURCE, esbmc_command=["esbmc"], bound=5,
                                  timeout_seconds=30, work_dir=work_dir, fixed_source=fixed)


def test_a_wrong_value_is_confirmed_when_the_fixed_version_keeps_the_property(tmp_path, monkeypatch):
    result = _run(tmp_path, monkeypatch, FakeLLM([GOOD]))
    assert result.verdict == VALUE_CONFIRMED
    assert result.replay["status"] == "property_violated" and result.replay["inputs"] == [-1]
    assert result.control["status"] == "not_reproduced"


def test_a_property_the_fixed_version_also_breaks_is_rejected(tmp_path, monkeypatch):
    wrong = json.dumps({"params": {"x": "int"}, "returns": "int", "postcondition": "result > 0"})
    assert _run(tmp_path, monkeypatch, FakeLLM([wrong])).verdict == PROPERTY_REJECTED


def test_without_a_fixed_version_the_violation_is_not_confirmed(tmp_path, monkeypatch):
    result = _run(tmp_path, monkeypatch, FakeLLM([GOOD]), fixed=None)
    assert result.verdict == VALUE_VIOLATION and "control" not in result.to_dict()


def test_a_missing_postcondition_goes_back_to_the_llm(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"x": "int"}, "returns": "int"}), GOOD])
    result = _run(tmp_path, monkeypatch, llm)
    assert "postcondition: missing" in llm.prompts[1]
    assert result.verdict == VALUE_CONFIRMED


def test_the_fixed_version_never_reaches_the_llm(tmp_path, monkeypatch):
    llm = FakeLLM([json.dumps({"params": {"x": "int"}}), GOOD])
    _run(tmp_path, monkeypatch, llm)
    assert len(llm.prompts) == 2
    assert all("FIXED_ONLY_MARKER" not in text and "else -x" not in text for text in [*llm.prompts, *llm.systems])


def test_the_value_prompt_is_only_for_value_hypotheses(tmp_path, monkeypatch):
    value = FakeLLM([GOOD])
    _run(tmp_path / "value", monkeypatch, value)
    assert value.systems[0].startswith(loop.SYSTEM_PROMPT) and "postcondition" in value.systems[0]
    assert "Kind: wrong result" in value.prompts[0]
    exception = FakeLLM([json.dumps({"params": {"x": "int"}})])
    _run(tmp_path / "exception", monkeypatch, exception, oracle="")
    assert exception.systems[0] == loop.SYSTEM_PROMPT and "Kind: wrong result" not in exception.prompts[0]


def test_run_verify_hands_the_fixed_file_only_to_value_hypotheses(tmp_path, monkeypatch):
    (tmp_path / "m.py").write_text(SOURCE, encoding="utf-8")
    fixed_dir = tmp_path / "fixed"
    fixed_dir.mkdir()
    (fixed_dir / "m.py").write_text(FIXED, encoding="utf-8")
    seen = {}

    def fake_verify(h, **kwargs):
        seen[h.oracle] = kwargs["fixed_source"]
        return loop.VerifyResult(h, "NOT_CONFIRMED")

    monkeypatch.setattr(loop, "verify_hypothesis", fake_verify)
    hypotheses = [BugHypothesis(str(tmp_path / "m.py"), "magnitude", "x if x > 0 else x", oracle=oracle)
                  for oracle in (VALUE_ORACLE, "")]
    loop.run_verify(hypotheses, llm=None, output_dir=tmp_path / "out", fixed_sources=fixed_dir)
    assert seen == {VALUE_ORACLE: FIXED, "": None}


class _Synthesizer:
    def __init__(self, **kwargs):
        self.model = kwargs["model"]


class _Nothing:
    def analyze(self, unit):
        return []


def test_main_passes_the_fixed_sources_to_verify(tmp_path, monkeypatch):
    source = tmp_path / "m.py"
    source.write_text(SOURCE, encoding="utf-8")
    captured = {}

    def fake_verify(hypotheses, **kwargs):
        captured.update(kwargs)
        return []

    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Nothing())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "run_verify", fake_verify)
    args = main.build_parser().parse_args(["--mode", "hybrid", "--input", str(source), "--output-dir",
                                           str(tmp_path / "out"), "--fixed-sources", str(tmp_path / "fixed")])
    assert main.mode_v2(args) == 0
    assert captured["fixed_sources"] == tmp_path / "fixed"
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_loop.py -q`
Expected: falhas com `TypeError: verify_hypothesis() got an unexpected keyword argument 'fixed_source'` e, no último, `error: unrecognized arguments: --fixed-sources`.

- [ ] **Passo 3: implementação**

`src/research_pipeline/prompts/value_property_prompt.txt` (novo):

```text
This hypothesis says the function returns a wrong value or leaves self in a wrong state; nothing
raises. Add two keys to the JSON object:

{"returns": "<type>", "postcondition": "<expr>"}

- returns: the type the function returns, from the allowed types except object; "None" when it
  returns nothing.
- postcondition: one boolean Python expression that every correct call satisfies, judged from the
  function's name, docstring, the code around it and the hypothesis. `result` is the returned value;
  it may also read the parameters and self.<attribute>, with their values after the call.
  Allowed: comparisons, and/or/not, + - *, len(x), isinstance(x, T) with T one of int, float, bool,
  str, bytes, list, dict, tuple, set, frozenset, `is None`, and membership in a tuple of constants.
  It must read result or a self.<attribute>; it cannot read result when returns is "None".
- Write what a correct function guarantees, not what this code computes: the checker looks for an
  input where this code breaks the postcondition.
```

`loop.py`: imports passam a incluir `from research_pipeline.models import ESBMCDirectResult`, `from .hypothesis import VALUE_ORACLE, BugHypothesis` (no lugar do import atual de `BugHypothesis`), `VALUE_VIOLATION` na lista de `from .outcome import (...)` e
`from .value_oracle import apply_control, check_fixed, esbmc_hits_property, value_verdict`. Depois de `SYSTEM_PROMPT = ...`:

```python
VALUE_PROMPT = (Path(__file__).resolve().parent.parent / "prompts" / "value_property_prompt.txt").read_text(encoding="utf-8")
```

Em `VerifyResult`, depois de `pytest: dict = ...`:

```python
    control: dict = field(default_factory=dict)
```

e no `to_dict`, depois da linha do `pytest`:

```python
            **({"control": self.control} if self.control else {}),
```

Em `_user_prompt`, antes de `if previous:`:

```python
    if h.oracle == VALUE_ORACLE:
        parts.insert(3, 'Kind: wrong result (nothing raises). Also give "returns" and "postcondition".')
```

`verify_hypothesis`: assinatura e docstring passam a ser

```python
def verify_hypothesis(
    h: BugHypothesis, *, llm: SpecLLM, source: str, esbmc_command: list[str] | None, bound: int,
    timeout_seconds: int, work_dir: Path, max_repairs: int = 2, replay_runs: int = 400,
    strategy: str = "repair", fixed_source: str | None = None,
) -> VerifyResult:
    """``strategy="resample"`` spends the same call budget on independent samples that never see
    the previous error: the baseline a guided repair has to beat (Olausson et al., ICLR 2024).
    ``fixed_source`` (evaluation only) is the fixed version of the file: a wrong-result hypothesis is
    replayed on it, after the LLM is done, with the input that broke the original."""
```

depois de `result = VerifyResult(h, "")`:

```python
    value = h.oracle == VALUE_ORACLE
    system = f"{SYSTEM_PROMPT}\n{VALUE_PROMPT}" if value else SYSTEM_PROMPT
```

a chamada ao LLM passa a usar `system`:

```python
        reply = llm.complete(system, _user_prompt(grounded, shown_previous, shown_feedback), json_mode=True)
```

a validação passa a ser `problems = spec_problems(spec, grounded, require_property=value)`, e, logo depois de `result.replay = replay.to_dict()`:

```python
        if value:
            return finish(*_value_outcome(result, reading, esbmc, program, grounded, replay, fixed_source))
```

Função nova, depois de `verify_hypothesis`:

```python
def _value_outcome(result: VerifyResult, reading: EsbmcReading, esbmc: ESBMCDirectResult, program: Program,
                   grounded: Grounded, replay: ReplayVerdict, fixed_source: str | None) -> tuple[str, str]:
    verdict = value_verdict(reading, esbmc_hits_property(esbmc, program.property_line), replay)
    if verdict != VALUE_VIOLATION or fixed_source is None:
        return verdict, reading.message
    control = check_fixed(program, grounded.hypothesis.function, grounded.method_name, fixed_source,
                          replay.inputs)
    result.control = control.to_dict()
    verdict, why = apply_control(verdict, control)
    return verdict, why or reading.message
```

`run_verify`: assinatura ganha `fixed_sources: Path | None = None` (depois de `strict_sources`), e a chamada passa a ser

```python
            data = verify_hypothesis(h, llm=llm, source=source, work_dir=Path(output_dir) / "programs",
                                     fixed_source=_fixed_source(h, fixed_sources), **kwargs).to_dict()
```

com a função nova:

```python
def _fixed_source(h: BugHypothesis, fixed_sources: Path | None) -> str | None:
    """Only a wrong-result hypothesis gets the fixed file, and only for the control after the LLM."""
    if fixed_sources is None or h.oracle != VALUE_ORACLE:
        return None
    path = Path(fixed_sources) / Path(h.file).name
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else None
```

`src/main.py`: depois do argumento `--verification-sources`:

```python
    parser.add_argument(
        "--fixed-sources",
        default=None,
        metavar="DIR",
        help="Motor verify: versões corrigidas (ex.: arquivo_corrigido) para o controle do oráculo de valor; "
             "o LLM nunca as vê.",
    )
```

em `_mode_v2_verify`, a chamada a `run_verify` ganha
`fixed_sources=Path(args.fixed_sources) if args.fixed_sources else None,`; e o dicionário `config` de `mode_v2` ganha `"fixed_sources": args.fixed_sources,` depois de `"verification_sources_strict"`.

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_loop.py tests/test_verify_loop.py tests/test_main_v2.py -q`
Expected: todos passam (8 novos).

- [ ] **Passo 5: suíte**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

- [ ] **Ponto de parada (sem commit).**

---

### Tarefa 7: roteamento e métrica

**Files:**
- Modify: `src/research_pipeline/verify/routing.py`
- Modify: `scripts/v2_orchestrate.py`
- Modify: `src/research_pipeline/verify/report.py`
- Test: `tests/test_verify_value_metric.py` (novo)

**Interfaces:**
- Consumes: `VALUE_ORACLE` (Tarefa 1), `VALUE_CONFIRMED` (Tarefa 5).
- Produces: `route(result)` devolve `()` para hipótese de valor; em `scripts/v2_orchestrate.py`, `_FORMAL` com os três vereditos novos, `api_agent_everywhere(result: dict) -> tuple[str, ...]`, e `summarize` com `value_confirmed_at_bug` e `confirmed_at_bug_with_value`; `evaluate_verify` com `value_confirmed_by_location`.

- [ ] **Passo 1: testes que falham**

```python
import importlib.util
from pathlib import Path

from research_pipeline.verify.candidate import Candidate
from research_pipeline.verify.orchestrator import orchestrate
from research_pipeline.verify.report import evaluate_verify
from research_pipeline.verify.routing import route

_SPEC = importlib.util.spec_from_file_location(
    "v2_orchestrate", Path(__file__).resolve().parents[1] / "scripts" / "v2_orchestrate.py")
v2_orchestrate = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(v2_orchestrate)

GT = {"a": {"function": "f", "expression": "x[i]", "crash_expressions": []}}


def _result(hid, expression, verdict="VALUE_CONFIRMED", oracle="value"):
    return {"verdict": verdict, "reason": "", "hypothesis": {
        "hypothesis_id": hid, "file": "d/a.py", "function": "f", "suspect_expression": expression, "oracle": oracle}}


def test_value_hypotheses_get_no_arm_whatever_stopped_them():
    assert route(_result("1", "x[i]", verdict="ESBMC_TIMEOUT")) == ()
    assert route(_result("1", "x[i]", verdict="ESBMC_TIMEOUT", oracle="")) != ()


def test_the_orchestrator_keeps_the_engine_value_verdict():
    calls = []
    rows = orchestrate([_result("1", "x[i]")], arms={"dynamic": lambda r: calls.append(r) or {"verdict": "FUZZ_FOUND"}},
                       state={}, save=lambda: None)
    assert calls == [] and rows[0]["final"] == "VALUE_CONFIRMED"


def test_value_confirmations_count_apart_and_only_at_the_bug_line():
    results = [_result("1", "x[i]"), _result("2", "y"), _result("3", "x[i]"), _result("4", "x[i]", oracle="")]
    rows = [{"hypothesis_id": "1", "final": "VALUE_CONFIRMED", "steps": []},
            {"hypothesis_id": "2", "final": "VALUE_CONFIRMED", "steps": []},
            {"hypothesis_id": "3", "final": "VALUE_VIOLATION", "steps": []},
            {"hypothesis_id": "4", "final": "CONFIRMED", "steps": []}]
    summary = v2_orchestrate.summarize(rows, results, GT)
    assert summary["value_confirmed_at_bug"] == 1 and summary["confirmed_at_bug"] == 1
    assert summary["confirmed_at_bug_with_value"] == 2


def test_the_api_agent_everywhere_route_skips_value_hypotheses():
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="ESBMC_TIMEOUT")) == ()
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="ESBMC_TIMEOUT", oracle="")) == ("api_agent",)
    assert v2_orchestrate.api_agent_everywhere(_result("1", "x[i]", verdict="PROPERTY_REJECTED", oracle="")) == ()


def test_the_report_counts_value_confirmations_by_location_apart():
    detection = Path("dataset/bugs_reais/funcao_com_bug/av_real_01.py")
    candidates = [Candidate(str(detection), "cli_bool_option", "", expression="assert isinstance(param, bool)")]
    result = {"verdict": "VALUE_CONFIRMED", "llm_calls": 1, "hypothesis": {
        "file": str(detection), "function": "cli_bool_option", "suspect_expression": "assert isinstance(param, bool)"}}
    evaluation = evaluate_verify([result], candidates, Path("dataset/bugs_reais/ground_truths.json"), [detection], [])
    assert evaluation["value_confirmed_by_location"]["expression"]["tp"] == 1
    assert evaluation["confirmed_by_location"]["expression"]["tp"] == 0
```

- [ ] **Passo 2: rodar e ver falhar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_metric.py -q`
Expected: 5 falhas (rota não vazia, braço chamado, chave `value_confirmed_at_bug` ausente, `api_agent_everywhere` inexistente, chave `value_confirmed_by_location` ausente).

- [ ] **Passo 3: implementação**

`routing.py`: import `from .hypothesis import VALUE_ORACLE` e `route` inteira:

```python
def route(result: dict) -> tuple[str, ...]:
    # Every arm looks for an exception; none knows a wrong-result hypothesis's property.
    if (result.get("hypothesis") or {}).get("oracle") == VALUE_ORACLE:
        return ()
    return _ROUTES[limit_class(result)]
```

`scripts/v2_orchestrate.py`:

```python
_FORMAL = {"CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED", "VALUE_CONFIRMED", "VALUE_VIOLATION", "PROPERTY_REJECTED"}
```

em `summarize`, o dicionário `summary` passa a ser montado assim:

```python
    found = [r for r in rows if r["final"] == FUZZ_FOUND and at_bug(r)]
    confirmed = sum(r["final"] == "CONFIRMED" and at_bug(r) for r in rows)
    # A wrong-result hypothesis counts only once the fixed version kept its property (VALUE_CONFIRMED).
    value = sum(r["final"] == "VALUE_CONFIRMED" and at_bug(r) for r in rows)
    summary = {"final": dict(Counter(r["final"] for r in rows)),
               "confirmed_at_bug": confirmed,
               "value_confirmed_at_bug": value,
               "confirmed_at_bug_with_value": confirmed + value,
               "fuzz_found_at_bug": len(found),
               "confirmed_at_bug_by_pinned": sum(
                   r["final"] == "CONFIRMED" and at_bug(r) and bool(r["steps"]) and r["steps"][-1]["arm"] == "pinned"
                   for r in rows)}
```

função nova depois de `agent_outcome`:

```python
def api_agent_everywhere(result: dict) -> tuple[str, ...]:
    """--api-agent-everywhere: every result without a formal verdict goes to api_agent, except a
    wrong-result hypothesis, whose property the agent does not know."""
    if result["verdict"] in _FORMAL or result["hypothesis"].get("oracle") == "value":
        return ()
    return ("api_agent",)
```

e, em `main`, a linha do `route` passa a ser
`route = api_agent_everywhere if args.api_agent_everywhere else None`.

`report.py`: import `from .outcome import CHECKED, CONFIRMED, VALUE_CONFIRMED, VERDICTS`, função nova e `evaluate_verify` reescrita:

```python
def _confirmed_by_location(results: list[dict], verdict: str, items: list[dict], base: Path) -> dict:
    found = [
        {"file": r["hypothesis"]["file"], "function": r["hypothesis"]["function"],
         "expression": r["hypothesis"]["suspect_expression"]}
        for r in results if r["verdict"] == verdict
    ]
    metrics = _bug_detection_metrics(items, found, base)
    metrics.pop("triage")  # every confirmed hypothesis was sent; triage says nothing here
    return metrics


def evaluate_verify(results: list[dict], candidates: list, ground_truth_path: str | Path,
                evaluated_sources: list, rejected_findings: list[dict]) -> dict:
    detection = evaluate_detection(candidates=candidates, ground_truth_path=ground_truth_path,
                                   evaluated_sources=evaluated_sources, rejected_findings=rejected_findings)
    items, base = _expected_items(Path(ground_truth_path), evaluated_sources)
    return {
        "triage": detection["triage"],
        "detection_by_location": detection["bug_detection"],
        "confirmed_by_location": _confirmed_by_location(results, CONFIRMED, items, base),
        # Kept apart: a wrong-result confirmation rests on an LLM-written property and the fixed-version control.
        "value_confirmed_by_location": _confirmed_by_location(results, VALUE_CONFIRMED, items, base),
    }
```

- [ ] **Passo 4: rodar e ver passar**

Run: `.venv/bin/python -m pytest tests/test_verify_value_metric.py tests/test_verify_routing.py tests/test_verify_orchestrator.py tests/test_v2_orchestrate.py tests/test_verify_report.py -q`
Expected: todos passam (5 novos).

- [ ] **Passo 5: suíte e lint**

Run: `timeout 10m .venv/bin/python -m pytest -q tests --ignore=tests/test_verify_esbmc_integration.py`
Expected: nenhuma falha.

Run: `pylint src/research_pipeline/verify/value_oracle.py src/research_pipeline/verify/spec.py src/research_pipeline/verify/render.py src/research_pipeline/verify/loop.py --disable=all --enable=E,W`
Expected: nenhum erro novo nos trechos alterados.

- [ ] **Ponto de parada (sem commit).** Registrar no `docs/projeto/PLANO_GERAL_2026-10-15.md`, item 5, que o oráculo está implementado e que a medição fica para o item 6 (comando previsto: detecção com `--v2-variants A15` e verify com `--fixed-sources dataset/bugs_reais/arquivo_corrigido`).
