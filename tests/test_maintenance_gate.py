import json

from research_pipeline.maintenance.gate import run_gate


def reference(tmp_path, confirmed=14):
    p = tmp_path / 'reference.json'
    p.write_text(json.dumps({'evaluation': {'confirmed_by_location': {'location': {'tp': confirmed}}}}))
    return p


def probes(accepted=True):
    return {'reason': 'sondas', 'results': {'p': {'outcome': 'aceita' if accepted else 'recusa'}}}


def test_gate_rejects_when_confirmed_bugs_drop_even_if_probes_improve(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'],
                      runner=lambda: probes(), baseline_probes=probes(False),
                      replay=lambda path: {'confirmed': 13, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True}, baseline_failures=[])
    assert result['verdict'] == 'REJEITADA'
    assert result['metrics']['bugs_confirmados']['antes'] == 14
    assert result['metrics']['bugs_confirmados']['depois'] == 13


def test_gate_reports_the_main_metric_before_the_intermediate_ones(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'],
                      runner=lambda: probes(), baseline_probes=probes(),
                      replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True, 'passed': 1}, baseline_failures=[],
                      baseline_passed=1)
    assert next(iter(result['metrics'])) == 'bugs_confirmados'
    assert result['verdict'] == 'ACEITA'


def test_gate_says_in_sample_when_no_holdout_is_given(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'],
                      runner=lambda: probes(), baseline_probes=probes(),
                      replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True}, baseline_failures=[])
    assert result['sample'] == 'dentro da amostra'


def test_gate_rejects_incomplete_evidence_and_regression_in_an_individual_probe(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'],
                      runner=lambda: probes(False), baseline_probes=probes(),
                      replay=lambda path: {'confirmed': 14, 'complete': False},
                      suite=lambda: {'failures': [], 'complete': True}, baseline_failures=[])
    assert result['verdict'] == 'REJEITADA'
    assert result['metrics']['sondas']['pioraram'] == ['p']
    assert any('incomplet' in reason for reason in result['reasons'])


def test_gate_rejects_when_suite_baseline_is_missing_or_failure_is_new(tmp_path):
    common = {'esbmc_command': ['esbmc'], 'runner': lambda: probes(), 'baseline_probes': probes(),
                  'replay': lambda path: {'confirmed': 14, 'complete': True},
                  'suite': lambda: {'failures': ['test_new'], 'complete': True}}
    assert run_gate(reference(tmp_path), **common)['verdict'] == 'REJEITADA'
    assert run_gate(reference(tmp_path), baseline_failures=['test_old'], **common)['metrics']['testes']['falhas_novas'] == ['test_new']


def test_unknown_baseline_probe_is_not_a_valid_comparison(tmp_path):
    old = {'reason': 'sondas', 'results': {'p': {'outcome': 'indeterminada'}}}
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'], runner=lambda: probes(),
                      baseline_probes=old, replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True}, baseline_failures=[])
    assert result['verdict'] == 'REJEITADA'


def test_replay_evidence_rejects_missing_cases_and_filled_types(tmp_path):
    from research_pipeline.maintenance.gate import recorded_replay

    original = tmp_path / 'original.json'
    original.write_text(json.dumps({'results': [{'hypothesis': {'hypothesis_id': 'a'}},
                                               {'hypothesis': {'hypothesis_id': 'b'}}]}))
    replay_dir = tmp_path / 'replay'
    replay_dir.mkdir()
    (replay_dir / 'report_0of1.json').write_text(json.dumps({'results': [{'hypothesis': {'hypothesis_id': 'a'}}]}))
    (replay_dir / 'replay_specs_0of1.json').write_text(json.dumps({'rows': [{'id': 'a', 'filled': 1}]}))
    result = recorded_replay(original, replay_dir, tmp_path / 'ground_truths.json')
    assert result['complete'] is False
    assert result['confirmed'] is None


def test_automatic_application_only_after_isolated_gate_accepts(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def evaluate(candidate):
        assert target.read_text() == 'value = 1\n'
        assert (candidate / 'src/research_pipeline/verify/example.py').read_text() == 'value = 2\n'
        return {'verdict': 'ACEITA'}
    result = apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=evaluate)
    assert result['applied'] is True
    assert target.read_text() == 'value = 2\n'


def test_automatic_application_preserves_original_if_gate_rejects(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    result = apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=lambda root: {'verdict': 'REJEITADA'})
    assert result['applied'] is False
    assert target.read_text() == 'value = 1\n'


def test_automatic_application_stops_if_original_changes_during_gate(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def evaluate(candidate):
        target.write_text('value = 3\n')
        return {'verdict': 'ACEITA'}
    result = apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=evaluate)
    assert result['applied'] is False
    assert target.read_text() == 'value = 3\n'


def test_automatic_application_rejects_patch_outside_verifier(tmp_path):
    import pytest

    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'secret.txt').write_text('old\n')
    patch = b'diff --git a/secret.txt b/secret.txt\n--- a/secret.txt\n+++ b/secret.txt\n@@ -1 +1 @@\n-old\n+new\n'
    with pytest.raises(ValueError, match='verificador'):
        apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=lambda root: {'verdict': 'ACEITA'})
    assert (repo / 'secret.txt').read_text() == 'old\n'


def test_isolated_candidate_does_not_share_artifact_contents(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    (repo / 'artifacts').mkdir()
    (repo / 'artifacts/data.txt').write_text('original')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def evaluate(candidate):
        (candidate / 'artifacts/data.txt').write_text('candidate')
        return {'verdict': 'REJEITADA'}
    apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=evaluate)
    assert (repo / 'artifacts/data.txt').read_text() == 'original'


def test_isolated_candidate_does_not_follow_original_artifact_symlinks(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    (repo / 'artifacts').mkdir()
    external = tmp_path / 'external.txt'
    external.write_text('original')
    (repo / 'artifacts/link.txt').symlink_to(external)
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def evaluate(candidate):
        (candidate / 'artifacts/link.txt').write_text('candidate')
        return {'verdict': 'REJEITADA'}
    apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=evaluate)
    assert external.read_text() == 'original'


def test_automatic_application_refuses_scratch_inside_repository(tmp_path):
    import pytest

    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    with pytest.raises(ValueError, match='fora'):
        apply_proposal(repo, patch, scratch=repo / 'scratch', evaluate=lambda root: {'verdict': 'REJEITADA'})


def test_automatic_application_stops_when_other_pipeline_code_changes(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    other = repo / 'src/research_pipeline/verify/other.py'
    other.write_text('other = 1\n')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def evaluate(candidate):
        other.write_text('other = 2\n')
        return {'verdict': 'ACEITA'}
    result = apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=evaluate)
    assert result['applied'] is False
    assert target.read_text() == 'value = 1\n'


def test_suite_evidence_distinguishes_failed_and_skipped(tmp_path):
    from research_pipeline.maintenance.gate import read_junit

    xml = tmp_path / 'suite.xml'
    xml.write_text('<testsuites><testsuite><testcase classname="tests.test_a" name="ok"/>'
                   '<testcase classname="tests.test_a" name="bad"><failure/></testcase>'
                   '<testcase classname="tests.test_a" name="skip"><skipped/></testcase>'
                   '</testsuite></testsuites>')
    result = read_junit(xml, returncode=1)
    assert result['complete'] is True
    assert result['passed'] == 1
    assert result['failures'] == ['tests.test_a::bad']


def test_suite_evidence_cannot_treat_interrupted_run_as_complete(tmp_path):
    from research_pipeline.maintenance.gate import read_junit

    xml = tmp_path / 'suite.xml'
    xml.write_text('<testsuites><testsuite><testcase classname="a" name="b"/></testsuite></testsuites>')
    assert read_junit(xml, returncode=124)['complete'] is False


def test_gate_reports_before_and_after_tests_passed(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'],
                      runner=lambda: probes(), baseline_probes=probes(),
                      replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True, 'passed': 21},
                      baseline_failures=[], baseline_passed=20)
    assert result['metrics']['testes']['antes'] == 20
    assert result['metrics']['testes']['depois'] == 21


def test_gate_rejects_when_pass_count_was_not_measured(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'], runner=lambda: probes(),
                      baseline_probes=probes(), replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True}, baseline_failures=[])
    assert result['verdict'] == 'REJEITADA'


def test_gate_rejects_if_fewer_tests_pass_without_new_failures(tmp_path):
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'], runner=lambda: probes(),
                      baseline_probes=probes(), replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True, 'passed': 19},
                      baseline_failures=[], baseline_passed=20)
    assert result['verdict'] == 'REJEITADA'
    assert 'Testes aprovados diminuíram' in result['reasons']


def test_recorded_replay_counts_bug_functions_in_copied_dataset(tmp_path):
    from research_pipeline.maintenance.gate import recorded_replay

    dataset = tmp_path / 'dataset'
    (dataset / 'funcao').mkdir(parents=True)
    (dataset / 'funcao/a.py').write_text('def f(): pass\n')
    truth = dataset / 'ground_truths.json'
    truth.write_text('{}')
    (dataset / 'manifest.json').write_text(json.dumps({'items': [{'id': 'a', 'detection_file': 'funcao/a.py',
        'function': 'f', 'expression': 'x', 'categories': ['error']}]}))
    reference = tmp_path / 'ref.json'
    hypothesis = {'hypothesis_id': 'abc', 'file': 'dataset/funcao/a.py', 'function': 'f', 'suspect_expression': 'x'}
    reference.write_text(json.dumps({'config': {'input_files': ['/different/repository/funcao/a.py']},
                                     'results': [{'hypothesis': hypothesis}]}))
    out = tmp_path / 'out'
    out.mkdir()
    (out / 'report_0of1.json').write_text(json.dumps({'results': [{'hypothesis': hypothesis, 'verdict': 'CONFIRMED'}]}))
    (out / 'replay_specs_0of1.json').write_text(json.dumps({'rows': [{'id': 'abc', 'filled': 0}]}))
    assert recorded_replay(reference, out, truth) == {'complete': True, 'confirmed': 1}


def test_automatic_candidate_does_not_copy_dotenv_secrets(tmp_path):
    from research_pipeline.maintenance.automatic import apply_proposal

    repo = tmp_path / 'repo'
    target = repo / 'src/research_pipeline/verify/example.py'
    target.parent.mkdir(parents=True)
    target.write_text('value = 1\n')
    (repo / '.env').write_text('TOKEN=secret\n')
    patch = b'diff --git a/src/research_pipeline/verify/example.py b/src/research_pipeline/verify/example.py\n--- a/src/research_pipeline/verify/example.py\n+++ b/src/research_pipeline/verify/example.py\n@@ -1 +1 @@\n-value = 1\n+value = 2\n'
    def evaluate(candidate):
        assert not (candidate / '.env').exists()
        return {'verdict': 'REJEITADA'}
    apply_proposal(repo, patch, scratch=tmp_path / 'scratch', evaluate=evaluate)


def test_gate_rejects_if_esbmc_identity_changed_between_probes(tmp_path):
    old = probes()
    old['identity'] = {'version': 'ESBMC v1', 'files': {'/esbmc': 'old'}}
    current = probes()
    current['identity'] = {'version': 'ESBMC v1', 'files': {'/esbmc': 'new'}}
    result = run_gate(reference(tmp_path), esbmc_command=['esbmc'], runner=lambda: current,
                      baseline_probes=old, replay=lambda path: {'confirmed': 14, 'complete': True},
                      suite=lambda: {'failures': [], 'complete': True, 'passed': 1},
                      baseline_failures=[], baseline_passed=1)
    assert result['verdict'] == 'REJEITADA'
    assert any('identidade' in reason for reason in result['reasons'])
