import json
import os
import subprocess
from pathlib import Path

import pytest

import main
from research_pipeline.verify import esbmc_provenance as provenance_module
from test_main_v2 import _Analyzer, _Synthesizer


def checkout(tmp_path):
    root = tmp_path / 'esbmc'
    (root / 'src/python-frontend').mkdir(parents=True)
    (root / 'src/python-frontend/README.md').write_text('# Python\n## Lists\nSupported.\n')
    docs = root / 'website/content/docs/python'
    docs.mkdir(parents=True)
    (docs / 'limitations.md').write_text('## Limits\nA limit.\n')
    (docs / 'supported-features.md').write_text('## Features\nA feature.\n')
    binary = root / 'build/src/esbmc/esbmc'
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\nprintf "ESBMC fake 1.0\\n"\n')
    binary.chmod(0o755)
    subprocess.run(['git', 'init', '-q', str(root)], check=True)
    subprocess.run(['git', '-C', str(root), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(root), '-c', 'user.name=Test', '-c', 'user.email=t@t',
                    'commit', '-qm', 'fixture'], check=True)
    commit_time = int(subprocess.check_output(['git', '-C', str(root), 'show', '-s', '--format=%ct']))
    os.utime(binary, (commit_time + 10, commit_time + 10))
    return root, binary, commit_time


def test_provenance_reads_binary_git_and_document_hashes(tmp_path):
    root, binary, _ = checkout(tmp_path)
    result = provenance_module.esbmc_provenance([str(binary)])
    assert result['binary'] == str(binary)
    assert result['version'] == 'ESBMC fake 1.0'
    assert result['repository_root'] == str(root)
    assert len(result['commit']) == 40
    assert result['dirty'] is False
    assert len(result['documents']) == 3
    assert all(len(value) == 64 for value in result['documents'].values())
    provenance_module.check_fresh(result)
    (root / 'src/python-frontend/README.md').write_text('changed')
    changed = provenance_module.esbmc_provenance([str(binary)])
    assert changed['dirty'] is True
    assert changed['documents'] != result['documents']


def test_old_binary_is_refused_with_rebuild_instruction(tmp_path):
    _, binary, timestamp = checkout(tmp_path)
    os.utime(binary, (timestamp - 10, timestamp - 10))
    with pytest.raises(ValueError, match='recompil'):
        provenance_module.check_fresh(provenance_module.esbmc_provenance([str(binary)]))


def test_wrapper_records_actual_binary_not_wrapper_date(tmp_path):
    root, binary, timestamp = checkout(tmp_path)
    wrapper = root / 'esbmc.sh'
    wrapper.write_text(f'#!/bin/sh\nexec {binary} "$@"\n')
    wrapper.chmod(0o755)
    os.utime(binary, (timestamp - 10, timestamp - 10))
    result = provenance_module.esbmc_provenance([str(wrapper)])
    assert result['binary'] == str(binary)
    with pytest.raises(ValueError, match='recompil'):
        provenance_module.check_fresh(result)


def run_args(tmp_path, binary):
    source = tmp_path / 'sample.py'
    source.write_text('def divide(x, y):\n    return x // y\n')
    return main.build_parser().parse_args(['--mode', 'hybrid', '--profile', 'congelado',
        '--v2-stage', 'detection', '--input', str(source), '--esbmc-command', str(binary),
        '--output-dir', str(tmp_path / 'out')])


def test_frozen_run_saves_provenance_and_refuses_changed_binary_on_resume(tmp_path, monkeypatch):
    _, binary, timestamp = checkout(tmp_path)
    args = run_args(tmp_path, binary)
    monkeypatch.setenv('OPENAI_API_KEY', 'fake')
    monkeypatch.setattr(main, 'build_analyzer', lambda **kw: _Analyzer())
    monkeypatch.setattr(main, 'LLMClient', _Synthesizer)
    assert main.mode_v2(args) == 0
    report = json.loads((Path(args.output_dir) / 'v2_verify_report.json').read_text())
    checkpoint = json.loads((Path(args.output_dir) / 'v2_checkpoint.json').read_text())
    assert report['config']['esbmc_provenance']['binary'] == str(binary)
    assert checkpoint['esbmc_provenance'] == report['config']['esbmc_provenance']
    assert checkpoint['fingerprint']['config']['esbmc_provenance'] == checkpoint['esbmc_provenance']
    os.utime(binary, (timestamp + 20, timestamp + 20))
    args.resume = True
    assert main.mode_v2(args) == 1


def test_stale_frozen_run_stops_before_building_analyzers(tmp_path, monkeypatch, capsys):
    _, binary, timestamp = checkout(tmp_path)
    os.utime(binary, (timestamp - 10, timestamp - 10))
    args = run_args(tmp_path, binary)
    monkeypatch.setattr(main, 'build_analyzer', lambda **kw: pytest.fail('must stop before LLM setup'))
    assert main.mode_v2(args) == 1
    assert 'recompil' in capsys.readouterr().err


def test_frozen_profile_wires_cache_and_function_metrics_to_final_report(tmp_path, monkeypatch):
    from research_pipeline.verify.capabilities import all_rules_report
    _, binary, _ = checkout(tmp_path)
    args = run_args(tmp_path, binary)
    args.v2_stage = 'end-to-end'
    gt = tmp_path / 'ground_truths.json'
    item = {'id': 'a', 'detection_file': 'sample.py', 'function': 'divide',
            'expression': 'x // y', 'categories': ['bug'], 'expected_type': 'ZeroDivisionError'}
    gt.write_text(json.dumps({'items': [item]}))
    (tmp_path / 'manifest.json').write_text(json.dumps({'items': [item]}))
    args.ground_truth = str(gt)
    monkeypatch.setenv('OPENAI_API_KEY', 'fake')
    monkeypatch.setattr(main, 'build_analyzer', lambda **kw: _Analyzer())
    monkeypatch.setattr(main, 'LLMClient', _Synthesizer)
    monkeypatch.setattr(main, 'resolve_rules', lambda *a, **kw: all_rules_report('fake'))
    captured = {}
    monkeypatch.setattr(main, 'build_healer', lambda *a, **kw: captured.update(kw))
    monkeypatch.setattr(main, 'run_verify', lambda hypotheses, **kw: [
        {'hypothesis': h.to_dict(), 'verdict': 'CONFIRMED', 'reason': '', 'attempts': [], 'llm_calls': 0,
         'replay': {'status': 'reproduced', 'exception_type': 'ZeroDivisionError'}} for h in hypotheses])
    assert main.mode_v2(args) == 0
    report = json.loads((Path(args.output_dir) / 'v2_verify_report.json').read_text())
    assert captured['kb_content_cache'] is True
    assert report['config']['kb_content_cache'] is True
    assert report['config']['evaluate_by_function'] is True
    assert report['evaluation']['by_function']['apontado_e_reproduzido'] == 1


def test_frozen_resolves_path_command_before_knowledge_lookup(tmp_path, monkeypatch):
    _, binary, _ = checkout(tmp_path)
    args = run_args(tmp_path, binary)
    args.esbmc_command = ['esbmc']
    monkeypatch.setenv('PATH', str(binary.parent) + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('OPENAI_API_KEY', 'fake')
    monkeypatch.setattr(main, 'build_analyzer', lambda **kw: _Analyzer())
    monkeypatch.setattr(main, 'LLMClient', _Synthesizer)
    assert main.mode_v2(args) == 0
    assert args.esbmc_command == [str(binary)]


def test_version_record_includes_binary_hash_without_running_verifier(tmp_path):
    metadata = {'commit': 'abc123', 'version': '8.6.0', 'binary': '/example/esbmc',
                'binary_sha256': 'f' * 64}
    path = tmp_path / 'versions.md'
    provenance_module.record_version(metadata, path)
    text = path.read_text()
    assert '| SHA-256 |' in text
    assert metadata['binary_sha256'] in text
    assert 'abc123' in text and '8.6.0' in text


def test_update_guard_preserves_known_untracked_launcher_but_rejects_other_changes(tmp_path):
    root, _, _ = checkout(tmp_path)
    wrapper = root / 'esbmc.sh'
    wrapper.write_text('#!/bin/sh\nexit 0\n')
    provenance_module.check_update_checkout(root)
    assert wrapper.read_text() == '#!/bin/sh\nexit 0\n'
    extra = root / 'untracked.cpp'
    extra.write_text('local source')
    with pytest.raises(ValueError, match='alterações locais'):
        provenance_module.check_update_checkout(root)


def test_update_guard_rejects_tracked_source_changes(tmp_path):
    root, _, _ = checkout(tmp_path)
    (root / 'src/python-frontend/README.md').write_text('local change')
    with pytest.raises(ValueError, match='alterações locais'):
        provenance_module.check_update_checkout(root)


def test_provenance_finds_checkout_when_build_dir_is_a_symlink_to_another_disk(tmp_path):
    root, binary, commit_time = checkout(tmp_path)
    elsewhere = tmp_path / 'other_disk_build'
    (root / 'build').rename(elsewhere)
    (root / 'build').symlink_to(elsewhere)
    result = provenance_module.esbmc_provenance([str(root / 'build/src/esbmc/esbmc')])
    assert result['repository_root'] == str(root)
    assert result['binary'] == str(elsewhere / 'src/esbmc/esbmc')
    assert len(result['commit']) == 40
