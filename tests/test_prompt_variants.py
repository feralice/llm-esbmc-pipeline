from pathlib import Path

import pytest

from research_pipeline.llm.example_pool import Example, ExamplePool, code_tokens
from research_pipeline.llm.findings import finding_from_dict, normalize_findings
from research_pipeline.llm.prompt_variants import apply_variants
from research_pipeline.llm.prompts import (
    build_user_prompt,
    load_system_prompt,
    set_context_sources,
    set_example_pool,
)
from research_pipeline.llm.schema import V2_FINDINGS_JSON_SCHEMA, v2_findings_schema
from research_pipeline.models import CodeUnit

BASE = load_system_prompt(include_smells=False, v2_detection=True)


def test_without_variants_the_prompt_is_the_baseline() -> None:
    assert apply_variants(BASE, ()) == BASE


def test_a1_asks_to_report_even_without_context() -> None:
    changed = apply_variants(BASE, ("A1",))
    assert "prefira não reportar" not in changed and "quando apropriado, não reporte" not in changed


def test_a2_adds_the_input_checklist_before_the_output_section() -> None:
    changed = apply_variants(BASE, ("A2",))
    assert changed.index("## PARTIÇÃO DE ENTRADAS") < changed.index("## SAÍDA")


def test_a3_asks_for_ranked_hypotheses() -> None:
    assert "da mais para a menos provável" in apply_variants(BASE, ("A3",))


def test_a6_makes_the_evidence_test_cover_any_wrong_behaviour() -> None:
    changed = apply_variants(BASE, ("A6",))
    assert "bloqueia EXATAMENTE o valor problemático" not in changed
    assert "3. A exceção é capturada" not in changed
    assert "valor diferente do que o código" in changed and "4. Existe valor concreto" in changed


def test_variants_compose() -> None:
    both = apply_variants(BASE, ("A1", "A2"))
    assert "## PARTIÇÃO DE ENTRADAS" in both and "prefira não reportar" not in both


def test_a_variant_whose_anchor_is_gone_fails_loudly() -> None:
    with pytest.raises(ValueError, match="A1"):
        apply_variants("prompt sem os trechos", ("A1",))


def test_an_unknown_variant_fails() -> None:
    with pytest.raises(ValueError, match="Z9"):
        apply_variants(BASE, ("Z9",))


def test_load_system_prompt_applies_variants() -> None:
    assert "## PARTIÇÃO DE ENTRADAS" in load_system_prompt(include_smells=False, v2_detection=True,
                                                           v2_variants=("A2",))


def _unit(path: Path, source: str, name: str = "f", start: int = 1, end: int = 2, qualname: str = "") -> CodeUnit:
    return CodeUnit(path=path, name=name, qualname=qualname or name, source=source, start_line=start, end_line=end,
                    parameters=[], type_hints={}, operations=[], loops=[], conditionals=[], guards=[], metrics={})


def test_a7_asks_for_the_analysis_first_in_prompt_and_schema() -> None:
    changed = apply_variants(BASE, ("A7",))
    assert "não produza uma cadeia de raciocínio" not in changed
    assert changed.index('"analysis"') < changed.index('"findings": [')
    schema = v2_findings_schema(("A7",))["schema"]
    assert next(iter(schema["properties"])) == "analysis" and "analysis" in schema["required"]


def test_without_variants_the_schema_is_the_baseline() -> None:
    assert v2_findings_schema(()) == V2_FINDINGS_JSON_SCHEMA


def test_a8_adds_worked_examples_before_the_output_section() -> None:
    changed = apply_variants(BASE, ("A8",))
    assert changed.index("## EXEMPLOS RESOLVIDOS") < changed.index("## SAÍDA")


def test_a9_asks_for_the_crash_site_in_prompt_and_schema() -> None:
    assert '"crash_expression"' in apply_variants(BASE, ("A9",))
    metadata = v2_findings_schema(("A9",))["schema"]["properties"]["findings"]["items"]["properties"]["metadata"]
    assert "crash_expression" in metadata["properties"] and "crash_expression" in metadata["required"]


def test_a9_a_distinct_crash_site_becomes_a_second_finding() -> None:
    raw = {"metadata": {"expression": "n = len(xs) - 1", "crash_expression": "xs[n + 1]"}, "verifiable": True}
    same = {"metadata": {"expression": "xs[0]", "crash_expression": "xs[0]"}, "verifiable": True}
    unit = _unit(Path("m.py"), "def f(xs): pass\n")
    found = normalize_findings(unit, [finding_from_dict(raw), finding_from_dict(same)], v2_detection=True)
    assert [f.metadata["expression"] for f in found] == ["n = len(xs) - 1", "xs[n + 1]", "xs[0]"]
    assert len({f.id for f in found}) == 3


def test_a10_keeps_the_docstring_only_when_asked() -> None:
    unit = _unit(Path("m.py"), 'def f(x):\n    """Devolve o dobro."""\n    return x * 2\n', end=3)
    assert "Devolve o dobro" not in build_user_prompt(unit, include_smells=False)
    assert "Devolve o dobro" in build_user_prompt(unit, include_smells=False, v2_variants=("A10",))
    assert apply_variants(BASE, ("A10",)) == BASE


def test_a11_adds_imports_class_outline_and_callers_from_the_same_file(tmp_path: Path) -> None:
    path = tmp_path / "mod.py"
    path.write_text(
        "import os\n"
        "class Box(Base):\n"
        "    def __init__(self, items=None):\n"
        "        self.items = items\n"
        "    def size(self):\n"
        "        return len(self.items)\n"
        "def report(box):\n"
        "    return box.size() + 1\n", encoding="utf-8")
    unit = _unit(path, "def size(self):\n    return len(self.items)\n", name="size", start=5, end=6,
                 qualname="Box.size")
    prompt = build_user_prompt(unit, include_smells=False, v2_variants=("A11",))
    block = prompt[prompt.index("<UNTRUSTED_CONTEXT_ARQUIVO>"):prompt.index("</UNTRUSTED_CONTEXT_ARQUIVO>")]
    assert "import os" in block and "class Box(Base):" in block and "self.items = items" in block
    assert "def report(box)" in block and "linha 8: return box.target_function() + 1" in block
    assert "size" not in block
    assert "<UNTRUSTED_CONTEXT_ARQUIVO>" not in build_user_prompt(unit, include_smells=False)
    assert "## CONTEXTO DO ARQUIVO" in apply_variants(BASE, ("A11",))


def test_a11_without_a_readable_file_adds_nothing(tmp_path: Path) -> None:
    unit = _unit(tmp_path / "missing.py", "def f(x):\n    return x\n")
    assert "UNTRUSTED_CONTEXT_ARQUIVO" not in build_user_prompt(unit, include_smells=False, v2_variants=("A11",))


def test_all_new_variants_compose_with_a5() -> None:
    changed = apply_variants(BASE, ("A1", "A2", "A7", "A8", "A9", "A10", "A11"))
    for marker in ("## PARTIÇÃO DE ENTRADAS", "## EXEMPLOS RESOLVIDOS", "## ONDE O BUG NASCE", "## CONTEXTO DO ARQUIVO",
                   '"analysis"', '"crash_expression"'):
        assert marker in changed


def test_a11_reads_the_context_from_the_full_file_when_detection_sees_a_slice(tmp_path: Path) -> None:
    (tmp_path / "slice").mkdir()
    (tmp_path / "full").mkdir()
    (tmp_path / "slice" / "m.py").write_text("class Box:\n    def size(self):\n        return len(self.items)\n",
                                            encoding="utf-8")
    (tmp_path / "full" / "m.py").write_text(
        "import os\nclass Box:\n    def __init__(self):\n        self.items = None\n"
        "    def size(self):\n        return len(self.items)\ndef report(box):\n    return box.size()\n",
        encoding="utf-8")
    unit = _unit(tmp_path / "slice" / "m.py", "def size(self):\n    return len(self.items)\n", name="size",
                 start=2, end=3, qualname="Box.size")
    set_context_sources(tmp_path / "full")
    try:
        prompt = build_user_prompt(unit, include_smells=False, v2_variants=("A11",))
    finally:
        set_context_sources(None)
    assert "self.items = None" in prompt and "def report(box)" in prompt


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


def test_new_variants_compose_with_a5_and_a9() -> None:
    changed = apply_variants(BASE, ("A1", "A2", "A9", "A13", "A14"))
    for marker in ("## PARTIÇÃO DE ENTRADAS", "## ONDE O BUG NASCE", "## EXEMPLOS DE BUGS REAIS",
                   "## EVIDÊNCIA CITADA", '"crash_expression"', '"quoted_line"', '"trigger"'):
        assert marker in changed
    assert changed.count("## SAÍDA: JSON válido") == 1
    assert changed.index("## EVIDÊNCIA CITADA") < changed.index("## SAÍDA")


def test_a13_renames_the_example_function_but_not_an_attribute_of_the_same_name() -> None:
    pool = ExamplePool(examples=(_example("b_1", "beta", "def update(conf, kwargs):\n    return conf.update(kwargs)\n",
                                          "update", "conf.update(kwargs) or update(conf, {})"),),
                       project_by_stem={})
    set_example_pool(pool)
    try:
        prompt = build_user_prompt(_unit(Path("m.py"), "def f(x):\n    return x\n"), include_smells=False,
                                   v2_variants=("A13",))
    finally:
        set_example_pool(None)
    assert "Bug corrigido pelos mantenedores: `conf.update(kwargs) or target_function(conf, {})`" in prompt
