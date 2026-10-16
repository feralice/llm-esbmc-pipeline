import importlib.util
import json
from pathlib import Path

from research_pipeline.verify.llm_client import SynthResult

_spec = importlib.util.spec_from_file_location("pcl", Path(__file__).parents[1] / "scripts/propose_crash_lines.py")
pcl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pcl)

SOURCE = "def f(xs, k):\n    window = get(k)\n    return xs[0] / window\n"


def test_pending_skips_wrong_results_and_already_labelled():
    items = [{"id": "a", "failure_kind": "excecao_local"},
             {"id": "b", "failure_kind": "resultado_errado"},
             {"id": "c", "failure_kind": "excecao_local", "crash_expressions": ["x"]}]
    assert [i["id"] for i in pcl.pending_items(items)] == ["a"]


def test_occurs_in_matches_spacing_and_return_prefix():
    assert pcl.occurs_in(SOURCE, "xs[0]/window")
    assert pcl.occurs_in(SOURCE, "return xs[0] / window")
    assert not pcl.occurs_in(SOURCE, "xs[1] / window")


def test_validate_discards_expressions_not_in_the_function():
    out = pcl.validate({"same_as_expression": False, "crash_expressions": ["xs[0] / window", "y / 0"],
                        "exception": "ZeroDivisionError", "reason": "r"}, SOURCE)
    assert out["crash_expressions"] == ["xs[0] / window"]
    assert out["discarded"] == ["y / 0"]


def test_validate_same_as_expression_ignores_the_list():
    out = pcl.validate({"same_as_expression": True, "crash_expressions": ["xs[0] / window"],
                        "exception": "E", "reason": "r"}, SOURCE)
    assert out["crash_expressions"] == [] and out["same_as_expression"]


def test_prompt_has_function_patch_and_cause_only():
    item = {"id": "a", "expression": "window = get(k)", "failure_kind_note": "divisão por zero"}
    prompt = pcl.build_prompt(item, SOURCE, "--- a\n+++ b\n")
    assert "window = get(k)" in prompt and "divisão por zero" in prompt and "+++ b" in prompt


class _LLM:
    def __init__(self, *replies):
        self.replies, self.calls = list(replies), 0

    def complete(self, system, user, *, json_mode=False):
        self.calls += 1
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return SynthResult(reply, reply, "fake", {})


def _dataset(tmp_path, ids):
    (tmp_path / "funcao_com_bug").mkdir(exist_ok=True)
    (tmp_path / "patches").mkdir(exist_ok=True)
    for i in ids:
        (tmp_path / "funcao_com_bug" / f"{i}.py").write_text(SOURCE)
        (tmp_path / "patches" / f"{i}.diff").write_text("--- a\n+++ b\n")
    return [{"id": i, "file": f"{i}.py", "failure_kind": "excecao_local", "expression": "window = get(k)"} for i in ids]


OK = json.dumps({"same_as_expression": False, "crash_expressions": ["xs[0] / window"], "exception": "E", "reason": "r"})


def test_propose_resumes_without_calling_again(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    pcl.propose(items, llm=_LLM(OK), dataset=tmp_path, out=out)
    llm = _LLM()
    pcl.propose(items, llm=llm, dataset=tmp_path, out=out)
    assert llm.calls == 0 and json.loads(out.read_text())["a"]["crash_expressions"] == ["xs[0] / window"]


def test_propose_stops_and_saves_on_usage_limit(tmp_path):
    items, out = _dataset(tmp_path, ["a", "b"]), tmp_path / "p.json"
    pcl.propose(items, llm=_LLM(OK, RuntimeError("claude -p saiu com código 1")), dataset=tmp_path, out=out)
    assert list(json.loads(out.read_text())) == ["a"]


def test_propose_retries_non_json_then_fails(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    saved = pcl.propose(items, llm=_LLM("x", "y", "z"), dataset=tmp_path, out=out)
    assert saved["a"]["status"] == "failed"


def test_missing_patch_is_marked(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    (tmp_path / "patches" / "a.diff").unlink()
    assert pcl.propose(items, llm=_LLM(), dataset=tmp_path, out=out)["a"]["status"] == "sem_patch"


def test_propose_stops_and_saves_on_timeout(tmp_path):
    items, out = _dataset(tmp_path, ["a", "b"]), tmp_path / "p.json"
    pcl.propose(items, llm=_LLM(OK, TimeoutError("Timeout ao chamar claude -p.")), dataset=tmp_path, out=out)
    assert list(json.loads(out.read_text())) == ["a"]


def _docs():
    def item():
        return {"id": "a", "label_sources": {"expression": "changed_line"}}
    return {"labels": [item()], "ground_truths": {"items": [item()]},
            "manifest": {"items": [item()]}, "manifest_full": {"items": [item()]}}


def test_apply_writes_accepted_into_all_documents_once():
    docs, props = _docs(), {"a": {"review": "aceita", "crash_expressions": ["xs[0] / window"]}}
    assert pcl.apply(props, docs) == 1
    assert pcl.apply(props, docs) == 0
    for doc in (docs["labels"], docs["ground_truths"]["items"], docs["manifest_full"]["items"]):
        assert doc[0]["crash_expressions"] == ["xs[0] / window"]
        assert doc[0]["label_sources"]["crash_expressions"] == "llm_patch_revisado"


def test_apply_skips_rejected_and_doubtful():
    docs = _docs()
    props = {"a": {"review": "rejeitada", "crash_expressions": ["x"]}}
    assert pcl.apply(props, docs) == 0 and "crash_expressions" not in docs["ground_truths"]["items"][0]


def test_review_table_shows_what_goes_into_the_ground_truth():
    props = {"a": {"status": "ok", "crash_expressions": ["xs[0] / window"], "exception": "ZeroDivisionError",
                   "review": "aceita", "review_note": "divisão logo abaixo", "same_as_expression": False,
                   "cause": {"status": "ambigua", "expressions": ["a.pop()"]}, "cause_review": "corrigida",
                   "cause_expressions_review": ["window = get(k)"], "cause_note": "só a segunda"}}
    table = pcl.review_table(props, {"a": {"expression": "window = get(k)", "failure_kind": "excecao_local"}})
    assert ("| a | excecao_local | `window = get(k)` | ambigua → corrigida: `window = get(k)` | só a segunda | "
            "aceita: `xs[0] / window` | ZeroDivisionError | divisão logo abaixo |") in table


def test_dump_keeps_the_original_trailing_newline():
    assert pcl.dump_like('[\n  1\n]', [1]) == '[\n  1\n]'
    assert pcl.dump_like('[\n  1\n]\n', [1]) == '[\n  1\n]\n'


PATCH = """--- a/pkg/m.py
+++ b/pkg/m.py
@@ -1,4 +1,4 @@
 def f(xs, k):
-    window = get(k)
+    window = get(k) or 1
     if window > 0:
-    return xs[0] / window
+    return xs[0] / window
--- a/pkg/other.py
+++ b/pkg/other.py
@@ -1,2 +1,2 @@
-    window = get(k)
+    pass
"""

SOURCE_IF = "def f(xs, k):\n    window = get(k)\n    if window > 0:\n        return xs[0] / window\n"


def test_removed_lines_only_from_the_target_file():
    assert pcl.removed_lines(PATCH, "pkg/m.py") == ["window = get(k)", "return xs[0] / window"]


def test_cause_matches_statements_by_text():
    out = pcl.cause_from_patch(SOURCE_IF, PATCH, "pkg/m.py")
    assert out == {"status": "ok", "expressions": ["window = get(k)", "return xs[0] / window"]}


def test_cause_uses_the_header_of_a_compound_statement():
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    if window > 0:\n+    if window:\n"
    assert pcl.cause_from_patch(SOURCE_IF, patch, "m.py")["expressions"] == ["window > 0"]


def test_insertion_only_patch():
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1,2 @@\n+    check(k)\n     window = get(k)\n"
    assert pcl.cause_from_patch(SOURCE_IF, patch, "m.py") == {"status": "so_insercao", "expressions": []}


def test_repeated_text_is_ambiguous():
    source = "def f(a):\n    a.pop()\n    a.pop()\n"
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    a.pop()\n+    a.clear()\n"
    out = pcl.cause_from_patch(source, patch, "m.py")
    assert out["status"] == "ambigua" and out["expressions"] == ["a.pop()"]


def test_no_match_in_the_function():
    patch = "--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    other()\n+    pass\n"
    assert pcl.cause_from_patch(SOURCE_IF, patch, "m.py")["status"] == "sem_casamento"


def test_propose_does_not_skip_a_bug_that_only_has_its_cause(tmp_path):
    items, out = _dataset(tmp_path, ["a"]), tmp_path / "p.json"
    out.write_text(json.dumps({"a": {"cause": {"status": "ok", "expressions": []}}}))
    saved = pcl.propose(items, llm=_LLM(OK), dataset=tmp_path, out=out)
    assert saved["a"]["status"] == "ok" and saved["a"]["cause"]["status"] == "ok"


def test_apply_writes_deterministic_causes_and_reviewed_ambiguous_ones():
    docs = _docs()
    props = {"a": {"cause": {"status": "ok", "expressions": ["window = get(k)", "xs[0] / window"]}}}
    assert pcl.apply(props, docs) == 1
    item = docs["ground_truths"]["items"][0]
    assert item["cause_expressions"] == ["window = get(k)", "xs[0] / window"]
    assert item["label_sources"]["cause_expressions"] == "patch"
    docs = _docs()
    assert pcl.apply({"a": {"cause": {"status": "ambigua", "expressions": ["a.pop()"]}}}, docs) == 0
    assert pcl.apply({"a": {"cause": {"status": "ambigua", "expressions": ["a.pop()"]},
                            "cause_review": "aceita"}}, docs) == 1


def test_clause_lines_and_docstrings_are_not_causes():
    source = ('def f(x):\n    """Doc line."""\n    try:\n        y = g(x)\n    except (TypeError, KeyError):\n'
              '        y = 0\n    if y:\n        h()\n    else:\n        k()\n')
    patch = ("--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    \"\"\"Doc line.\"\"\"\n-    try:\n"
             "-    except (TypeError, KeyError):\n-    else:\n-        y = g(x)\n+    pass\n")
    assert pcl.cause_from_patch(source, patch, "m.py") == {"status": "ok", "expressions": ["y = g(x)"]}


def test_causes_cover_wrong_result_bugs_too(tmp_path):
    items = _dataset(tmp_path, ["a"])
    items[0]["failure_kind"] = "resultado_errado"
    (tmp_path / "patches" / "a.diff").write_text("--- a/m.py\n+++ b/m.py\n@@ -1 +1 @@\n-    window = get(k)\n+    w = 1\n")
    saved = pcl.causes(items, dataset=tmp_path, out=tmp_path / "p.json")
    assert saved["a"]["cause"] == {"status": "ok", "expressions": ["window = get(k)"]}


def test_merge_reviews_validates_expressions_and_marks_corrections():
    props = {"a": {"status": "ok", "crash_expressions": ["xs[1]"], "cause": {"status": "ambigua", "expressions": []}}}
    reviews = [{"id": "a", "review": "rejeitada", "crash_expressions_review": ["xs[0] / window", "nope(1)"],
                "review_note": "n", "cause_review": "corrigida", "cause_expressions_review": ["window = get(k)"],
                "cause_note": "c"}]
    pcl.merge_reviews(props, reviews, {"a": SOURCE})
    entry = props["a"]
    assert entry["review"] == "corrigida" and entry["crash_expressions_review"] == ["xs[0] / window"]
    assert entry["cause_review"] == "corrigida" and entry["cause_expressions_review"] == ["window = get(k)"]
    assert "nope(1)" in entry["review_note"]


def test_merge_reviews_without_valid_correction_becomes_doubt():
    props = {"a": {"status": "ok", "crash_expressions": ["xs[1]"], "cause": {"status": "ok", "expressions": []}}}
    pcl.merge_reviews(props, [{"id": "a", "review": "rejeitada", "crash_expressions_review": ["nope(1)"],
                               "review_note": "n", "cause_review": "aceita", "cause_note": ""}], {"a": SOURCE})
    assert props["a"]["review"] == "rejeitada"


def test_apply_uses_reviewed_corrections():
    docs = _docs()
    props = {"a": {"review": "corrigida", "crash_expressions": ["wrong"], "crash_expressions_review": ["xs[0] / window"],
                   "cause": {"status": "so_insercao", "expressions": []}, "cause_review": "corrigida",
                   "cause_expressions_review": ["window = get(k)"]}}
    assert pcl.apply(props, docs) == 1
    item = docs["ground_truths"]["items"][0]
    assert item["crash_expressions"] == ["xs[0] / window"] and item["cause_expressions"] == ["window = get(k)"]
    assert item["label_sources"]["cause_expressions"] == "patch_revisado"
