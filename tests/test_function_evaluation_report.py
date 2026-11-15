import json

from research_pipeline import v2_evaluator


def test_report_warns_when_every_available_function_is_labelled(tmp_path):
    (tmp_path / 'a.py').write_text('def f(x):\n    return x[0]\n')
    items = [{'id': 'a', 'detection_file': 'a.py', 'function': 'f', 'categories': ['bug'],
              'expected_type': 'IndexError'}]
    candidate = {'file': str(tmp_path / 'a.py'), 'function': 'f', 'expression': 'x[0]'}
    metrics = v2_evaluator.evaluate_functions(items, [candidate], tmp_path, results=[])
    text = v2_evaluator.render_function_evaluation(metrics)
    assert 'não tem poder de discriminação' in text
    assert '1 arquivos' in text and '1 funções' in text
    assert 'Apontado e reproduzido' in text
    assert 'Confirmado pelo ESBMC' in text
    assert text.index('Apontado e reproduzido') < text.index('Apontado (apoio)')


def test_a_perfect_score_alone_does_not_imply_trivial_input_design(tmp_path):
    (tmp_path / 'a.py').write_text('def f(x):\n    return x[0]\ndef clean(x):\n    return x\n')
    items = [{'id': 'a', 'detection_file': 'a.py', 'function': 'f', 'categories': ['bug']}]
    metrics = v2_evaluator.evaluate_functions(items, [
        {'file': str(tmp_path / 'a.py'), 'function': 'f'}], tmp_path)
    assert metrics['apontado'] == metrics['total'] == 1
    assert 'não tem poder de discriminação' not in v2_evaluator.render_function_evaluation(metrics)


def test_report_distinguishes_missing_sources_and_unmeasured_replay(tmp_path):
    items = [{'id': 'a', 'detection_file': 'missing.py', 'function': 'f', 'categories': ['bug']}]
    metrics = v2_evaluator.evaluate_functions(items, [], tmp_path)
    text = v2_evaluator.render_function_evaluation(metrics)
    assert 'não medido' in text
    assert 'não foi possível conferir' in text
    assert 'não tem poder de discriminação' not in text


def test_available_fix_judge_is_highlighted_without_inventing_missing_data():
    metrics = {'total': 47, 'apontado': 47, 'apontado_e_reproduzido': 8,
               'confirmado_esbmc': 5, 'mesmo_padrao_em_outra_funcao': []}
    text = v2_evaluator.render_function_evaluation(metrics, fix_judge={'fixed_ok': 4, 'source': 'saved.json'})
    assert '**Juiz do conserto: 4' in text
    assert 'saved.json' in text
    assert 'Juiz do conserto: 4' not in v2_evaluator.render_function_evaluation(metrics)


def test_cli_writes_function_evaluation_text_when_enabled(tmp_path, monkeypatch):
    from test_main_v2 import _run_config
    item = {'id': 'a', 'detection_file': 'sample.py', 'function': 'divide', 'categories': ['bug']}
    (tmp_path / 'manifest.json').write_text(json.dumps({'items': [item]}))
    gt = tmp_path / 'ground_truths.json'
    gt.write_text(json.dumps({'items': [item]}))
    _run_config(tmp_path, monkeypatch, '--evaluate-by-function', '--ground-truth', str(gt))
    report = tmp_path / 'out/avaliacao_funcoes.md'
    assert report.exists()
    assert 'não tem poder de discriminação' in report.read_text()


def test_disabled_option_does_not_create_a_presentation_file(tmp_path, monkeypatch):
    from test_main_v2 import _run_config
    _run_config(tmp_path, monkeypatch)
    assert not (tmp_path / 'out/avaliacao_funcoes.md').exists()
