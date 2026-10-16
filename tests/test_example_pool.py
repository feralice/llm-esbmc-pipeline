import json
from pathlib import Path

from research_pipeline.llm.example_pool import (
    code_tokens,
    load_example_pool,
    select_examples,
    similarity,
)
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


def test_tokens_of_a_function_with_a_bad_escape_emit_no_warning(recwarn) -> None:
    assert "re" in code_tokens("def f(s):\n    return re.sub('\\s', '', s)\n")
    assert not [w for w in recwarn if issubclass(w.category, SyntaxWarning)]
