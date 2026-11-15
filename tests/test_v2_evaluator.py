from __future__ import annotations

import json

import pytest

from research_pipeline.v2_evaluator import (
    _bug_detection_metrics,
    at_bug_line,
    evaluate_detection,
    expressions_equivalent,
)
from research_pipeline.verify.candidate import Candidate


def test_detection_counts_one_true_positive_and_ignores_duplicates_by_location(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "bug.py"
    source.write_text("def f(x: int) -> int:\n    return 1 // x\n", encoding="utf-8")
    (tmp_path / "bugs").mkdir()
    (tmp_path / "bugs" / "bug.py").write_text("assert False\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "b1", "categories": ["division_by_zero"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "b1", "detection_file": "detection/bug.py",
            "harness_file": "bugs/bug.py", "categories": ["division_by_zero"],
        }]}),
        encoding="utf-8",
    )
    correct = Candidate(str(source), "f", "division_by_zero")
    false_positive = Candidate(str(source), "f", "out_of_bounds")
    metrics = evaluate_detection(candidates=[correct, false_positive],
        ground_truth_path=tmp_path / "ground_truths.json",
    )

    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fp"] == 0
    assert metrics["detection"]["fn"] == 0


def test_v2_reports_location_whatever_the_category_label(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "bug.py"
    source.write_text("def f(x: int) -> int:\n    return 1 // x\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "b1", "categories": ["division_by_zero"]}]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "b1", "detection_file": "detection/bug.py", "function": "f",
            "expression": "1 // x", "harness_file": "bugs/bug.py",
            "categories": ["division_by_zero"],
        }]}),
        encoding="utf-8",
    )
    wrong_category = Candidate(str(source), "f", "none_misuse", expression="1 // x")

    metrics = evaluate_detection(candidates=[wrong_category],
        ground_truth_path=tmp_path / "ground_truths.json",
    )

    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fp"] == 0
    assert metrics["detection"]["fn"] == 0
    assert metrics["bug_detection"]["file"]["tp"] == 1
    assert metrics["bug_detection"]["location"]["tp"] == 1
    assert metrics["bug_detection"]["expression"]["tp"] == 1


def test_v2_excludes_patch_context_items_from_detection_metrics(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    first = detection / "first.py"
    second = detection / "second.py"
    source = "def f(x: int) -> int:\n    return 1 // x\n"
    first.write_text(source, encoding="utf-8")
    second.write_text(source, encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [
            {"id": "b1", "categories": ["division_by_zero"]},
            {"id": "b2", "categories": ["assertion_violation"]},
        ]}),
        encoding="utf-8",
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({
            "evaluation_policy": {"patch_context_items": ["b2"]},
            "items": [
                {"id": "b1", "detection_file": "detection/first.py", "categories": ["division_by_zero"]},
                {"id": "b2", "detection_file": "detection/second.py", "categories": ["assertion_violation"]},
            ],
        }),
        encoding="utf-8",
    )
    candidate = Candidate(str(first), "f", "division_by_zero")
    metrics = evaluate_detection(candidates=[candidate],
        ground_truth_path=tmp_path / "ground_truths.json",
    )
    assert metrics["excluded_patch_context_items"] == 1
    assert metrics["detection"]["tp"] == 1
    assert metrics["detection"]["fn"] == 0


def test_ast_rejection_remains_a_detection_false_positive(tmp_path) -> None:
    detection = tmp_path / "detection"
    detection.mkdir()
    source = detection / "clean.py"
    source.write_text("def f(x: int) -> int:\n    return x\n", encoding="utf-8")
    (tmp_path / "ground_truths.json").write_text(
        json.dumps({"items": [{"id": "c1", "categories": []}]}), encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        json.dumps({"items": [{
            "id": "c1", "detection_file": "detection/clean.py",
            "harness_file": "bugs/clean.py", "categories": [],
        }]}),
        encoding="utf-8",
    )
    metrics = evaluate_detection(candidates=[], ground_truth_path=tmp_path / "ground_truths.json",
        rejected_findings=[{
            "file": str(source), "category": "division_by_zero",
            "finding_type": "llm_false_positive",
        }],
    )
    assert metrics["detection"]["fp"] == 1




@pytest.mark.parametrize("expected, found, same", [
    ("float(a)/float(b)", "float(a) / float(b)", True),
    ("':' not in self._url", "if ':' not in self._url:", True),
    ("x[0]", "return x[0]", True),
    ("'open ' + s[5:]", "s[5:]", True),
    ("self.iterable = iterable", "self.set_postfix(refresh=False)", False),
    ("a // b", "a // c", False),
    ("self.iterable = iterable", "iterable", False),
    ("self.x + 1", "self.x", False),
    ("self.a.b[0]", "if self.a.b[0]:", True),
    ("", "a // b", False),
    ("IOLoop.current(instance=False) is None",
     "if IOLoop.current(instance=False) is None:\n            raise RuntimeError('exists')", True),
    ("(h - w) / s", "for h in range(math.ceil((h - w) / s) + 1):", True),
    ("open(context_file)", "with open(context_file) as fh:", True),
    ("ret[mask] = False", "if op not in {'__eq__'}:\n    mask = codes == -1\n    ret[mask] = False", True),
    ("self.iterable = iterable", "self.iterable = iterable\nself.disable = disable", False),
    ("ret[mask] = False", "if op:\n    ret[other] = False", False),
])
def test_expressions_equivalent(expected, found, same):
    assert expressions_equivalent(expected, found) is same


def test_equivalent_expression_metric_sits_beside_the_exact_one(tmp_path):
    item = {"detection_file": "d.py", "function": "f", "expression": "float(a)/float(b)",
            "categories": ["division_by_zero"]}
    base = str((tmp_path / "d.py").resolve())
    same_function = {"file": base, "function": "f", "expression": "float(a) / float(b)", "category": "x"}
    other_function = {"file": base, "function": "g", "expression": "float(a)/float(b)", "category": "x"}
    metrics = _bug_detection_metrics([item], [same_function, other_function], tmp_path)
    assert metrics["expression"]["tp"] == 0
    assert metrics["expression_equivalent"]["tp"] == 1
    assert metrics["expression_equivalent"]["fp"] == 1


def test_at_bug_line_accepts_any_cause_line_from_the_patch():
    item = {"function": "f", "expression": "window = get(k)", "cause_expressions": ["k = k or 1"]}
    assert at_bug_line({"function": "f", "suspect_expression": "k = k or 1"}, item)
    assert not at_bug_line({"function": "f", "suspect_expression": "other()"}, item)


def test_function_metrics_ignore_expression_but_require_matching_replay_exception(tmp_path):
    from research_pipeline.v2_evaluator import evaluate_functions
    items = [{'id': 'a', 'detection_file': 'a.py', 'function': 'f / g', 'categories': ['bug'],
              'expression': 'labelled()', 'expected_type': 'IndexError'},
             {'id': 'b', 'detection_file': 'b.py', 'function': 'f', 'categories': ['bug'],
              'expected_type': 'struct.error'}]
    candidates = [{'file': str(tmp_path / 'a.py'), 'function': 'g', 'expression': 'other()'},
                  {'file': str(tmp_path / 'a.py'), 'function': 'g', 'expression': 'duplicate()'},
                  {'file': str(tmp_path / 'b.py'), 'function': 'f', 'expression': 'any()'}]
    results = [{'hypothesis': {'file': c['file'], 'function': c['function']}, 'verdict': verdict,
                'replay': {'status': 'reproduced', 'exception_type': exception}}
               for c, verdict, exception in [(candidates[0], 'CONFIRMED', 'IndexError'),
                                             (candidates[2], 'CONFIRMED', 'TypeError')]]
    metrics = evaluate_functions(items, candidates, tmp_path, results=results)
    assert metrics['total'] == metrics['apontado'] == 2
    assert metrics['apontado_e_reproduzido'] == metrics['confirmado_esbmc'] == 1
    assert metrics['cases'][1]['apontado_e_reproduzido'] is False
    detection_only = evaluate_functions(items, candidates, tmp_path)
    assert detection_only['apontado_e_reproduzido'] is None
    assert detection_only['confirmado_esbmc'] is None


def test_function_metrics_keep_sisters_separate_and_exclude_broad_patches(tmp_path):
    from research_pipeline.v2_evaluator import evaluate_functions
    items = [{'id': name, 'detection_file': name + '.py', 'function': 'f',
              'categories': ['bug'], 'expected_type': 'IndexError'}
             for name in ('case', 'cps_pymodbus_2977', 'cps_pycomm3_331', 'cps_gps_127')]
    siblings = [{'id': item['id'], 'tocadas_pelo_patch': ['f', 'sister']} for item in items]
    candidates = [{'file': str(tmp_path / item['detection_file']), 'function': 'sister', 'expression': 'x[0]'}
                  for item in items]
    metrics = evaluate_functions(items, candidates, tmp_path, results=[], sibling_labels=siblings)
    assert metrics['apontado'] == metrics['apontado_e_reproduzido'] == 0
    assert [r['id'] for r in metrics['mesmo_padrao_em_outra_funcao']] == ['case']
    assert metrics['mesmo_padrao_em_outra_funcao'][0]['functions'] == ['sister']


def test_function_replay_other_line_counts_only_inside_target(tmp_path):
    from research_pipeline.v2_evaluator import evaluate_functions
    items = [{'id': 'a', 'detection_file': 'a.py', 'function': 'f', 'categories': ['bug'],
              'expected_type': 'IndexError'}]
    candidates = [{'file': str(tmp_path / 'a.py'), 'function': 'f', 'expression': 'x[0]'}]
    result = {'hypothesis': candidates[0], 'verdict': 'OTHER_FAILURE',
              'replay': {'status': 'other_failure', 'exception_type': 'IndexError',
                         'line': 15, 'target_range': [10, 20]}}
    assert evaluate_functions(items, candidates, tmp_path, results=[result])['apontado_e_reproduzido'] == 1
    result['replay']['line'] = 4
    assert evaluate_functions(items, candidates, tmp_path, results=[result])['apontado_e_reproduzido'] == 0


def test_function_metric_flag_preserves_existing_evaluation(tmp_path):
    items = [{'id': 'a', 'detection_file': 'a.py', 'function': 'f', 'categories': ['bug'],
              'expression': 'x[0]', 'expected_type': 'IndexError'}]
    (tmp_path / 'manifest.json').write_text(json.dumps({'items': items}))
    gt = tmp_path / 'ground_truths.json'
    gt.write_text(json.dumps({'items': items}))
    candidates = [{'file': str(tmp_path / 'a.py'), 'function': 'f', 'expression': 'different()'}]
    before = evaluate_detection(candidates=candidates, ground_truth_path=gt)
    after = evaluate_detection(candidates=candidates, ground_truth_path=gt, evaluate_by_function=True)
    assert after.pop('by_function')['apontado'] == 1
    assert after == before


def test_review_dropped_hypothesis_still_counts_only_in_new_metrics(tmp_path):
    items = [{'id': 'a', 'detection_file': 'a.py', 'function': 'f', 'categories': ['bug'],
              'expression': 'x[0]', 'expected_type': 'IndexError'}]
    (tmp_path / 'manifest.json').write_text(json.dumps({'items': items}))
    gt = tmp_path / 'ground_truths.json'
    gt.write_text(json.dumps({'items': items}))
    dropped = {'file': str(tmp_path / 'a.py'), 'function': 'f', 'expression': 'different()'}
    before = evaluate_detection(candidates=[], ground_truth_path=gt)
    after = evaluate_detection(candidates=[], ground_truth_path=gt, evaluate_by_function=True,
                               additional_findings=[dropped], results=[])
    by_function = after.pop('by_function')
    assert by_function['apontado'] == 1
    assert by_function['apontado_e_reproduzido'] == 0
    assert after == before
