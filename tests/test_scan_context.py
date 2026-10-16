from pathlib import Path

from research_pipeline.llm.prompts import build_user_prompt
from research_pipeline.models import CodeUnit
from research_pipeline.scan.callgraph import build_callgraph
from research_pipeline.scan.context import NO_CALLERS, caller_context


def _graph(tmp_path: Path, text: str):
    (tmp_path / "m.py").write_text(text, encoding="utf-8")
    return build_callgraph(tmp_path)


SOURCE = (
    "def ratio(a, b):\n"          # 1
    "    return a / b\n"          # 2
    "\n"                          # 3
    "def other():\n"              # 4
    "    return 42\n"             # 5
    "def caller(xs):\n"           # 6
    "    n = len(xs)\n"           # 7
    "    if n == 0:\n"            # 8
    "        return 0\n"          # 9
    "    return ratio(1, n)\n"    # 10
    "result = ratio(4, 2)\n"      # 11
)


def test_context_shows_the_guard_before_the_call_and_renames_the_target(tmp_path: Path) -> None:
    text = caller_context(_graph(tmp_path, SOURCE), "m:ratio")
    assert "# chamada em caller, m.py, linha 10:" in text
    assert "    8 |     if n == 0:" in text and "   10 |     return target_function(1, n)" in text
    assert "# chamada em nível de módulo, m.py, linha 11:" in text
    assert "ratio" not in text


def test_context_never_leaks_lines_of_a_neighbouring_function(tmp_path: Path) -> None:
    source = "def f(x):\n    return 1 / x\ndef g():\n    return 7\ndef h():\n    return f(0)\n"
    text = caller_context(_graph(tmp_path, source), "m:f", before=5)
    assert "return 7" not in text and "    5 | def h():" in text


def test_context_keeps_the_caller_signature_when_the_window_starts_later(tmp_path: Path) -> None:
    text = caller_context(_graph(tmp_path, SOURCE), "m:ratio", before=1)
    assert "    6 | def caller(xs):" in text and "      | ..." in text
    assert "    7 |" not in text


def test_context_is_capped_and_says_how_many_calls_were_left_out(tmp_path: Path) -> None:
    body = "".join(f"    f({i})\n" for i in range(30))
    text = caller_context(_graph(tmp_path, "def f(x):\n    return x\ndef g():\n" + body), "m:f",
                          before=0, after=0, max_sites=50, max_chars=300)
    assert len(text) < 400
    assert "chamada(s) omitida(s)" in text


def test_context_without_callers_says_so(tmp_path: Path) -> None:
    assert caller_context(_graph(tmp_path, "def f(x):\n    return x\n"), "m:f") == NO_CALLERS


def _unit(context: str) -> CodeUnit:
    return CodeUnit(path=Path("m.py"), name="f", qualname="f", source="def f(x):\n    return 1 / x\n",
                    start_line=1, end_line=2, parameters=["x"], type_hints={}, operations=[], loops=[],
                    conditionals=[], guards=[], metrics={}, caller_context=context)


def test_a12_puts_the_caller_block_in_the_user_prompt_only_when_asked() -> None:
    unit = _unit("# chamada em g, m.py, linha 9:")
    assert "<UNTRUSTED_CONTEXT_CHAMADORES>\n# chamada em g" in build_user_prompt(
        unit, include_smells=False, v2_variants=("A12",))
    assert "CHAMADORES" not in build_user_prompt(unit, include_smells=False)
    assert "CHAMADORES" not in build_user_prompt(_unit(""), include_smells=False, v2_variants=("A12",))


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
