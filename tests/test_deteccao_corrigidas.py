import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from preparar_deteccao_corrigidas import prepare  # noqa: E402
from research_pipeline.preprocess import preprocess_file  # noqa: E402


def fixture(tmp_path):
    dataset = tmp_path / 'dataset'
    (dataset / 'funcao_com_bug').mkdir(parents=True)
    (dataset / 'arquivo_corrigido').mkdir()
    (dataset / 'funcao_com_bug/a.py').write_text('class C:\n    def f(self, x):\n        return 1 / x\n')
    (dataset / 'arquivo_corrigido/a.py').write_text(
        'import math\nclass C:\n    @staticmethod\n    def helper():\n        return 777\n'
        '    def f(self, x):\n        if x == 0:\n            return 0\n        return 1 / x\n')
    report = tmp_path / 'reference.json'
    report.write_text(json.dumps({'config': {'profile': 'congelado', 'backend': 'claude_cli',
        'model': 'test-model', 'v2_variants': ['A1', 'A2'], 'v2_stage': 'end-to-end',
        'input_files': [str(dataset / 'funcao_com_bug/a.py')], 'claude_isolated': True},
        'results': []}))
    return dataset, report


def test_preparation_extracts_only_paired_fixed_functions_and_keeps_model(tmp_path):
    dataset, reference = fixture(tmp_path)
    output = tmp_path / 'out'
    data = prepare(reference, dataset, output)
    source = (output / 'funcao_corrigida/a.py').read_text()
    assert 'if x == 0:' in source
    assert 'helper' not in source and 'import math' not in source
    assert [u.qualname for u in preprocess_file(output / 'funcao_corrigida/a.py')] == ['C.f']
    command = data['command']
    assert command[command.index('--v2-stage') + 1] == 'detection'
    assert command[command.index('--profile') + 1] == 'congelado'
    assert command[command.index('--model') + 1] == 'test-model'
    assert command[command.index('--v2-variants') + 1] == 'A1,A2'
    assert '--ground-truth' not in command and '--verification-sources' not in command
    assert data['estimated_calls'] == 1
    assert data['estimated_tokens_53_functions'] == 80000
    assert (output / 'preparacao.json').exists()
    assert (output / 'commit.txt').exists()


def test_missing_fixed_function_fails_before_creating_output(tmp_path):
    dataset, reference = fixture(tmp_path)
    (dataset / 'arquivo_corrigido/a.py').write_text('def other():\n    pass\n')
    with pytest.raises(ValueError, match='C.f'):
        prepare(reference, dataset, tmp_path / 'out')
    assert not (tmp_path / 'out').exists()


def test_nonfrozen_reference_is_not_silently_compared_with_frozen(tmp_path):
    dataset, reference = fixture(tmp_path)
    data = json.loads(reference.read_text())
    data['config'].pop('profile')
    reference.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='congelado'):
        prepare(reference, dataset, tmp_path / 'out')


def test_existing_output_is_preserved(tmp_path):
    dataset, reference = fixture(tmp_path)
    output = tmp_path / 'out'
    output.mkdir()
    marker = output / 'keep'
    marker.write_text('old')
    with pytest.raises(ValueError, match='existe'):
        prepare(reference, dataset, output)
    assert marker.read_text() == 'old'


def test_reference_esbmc_flags_remain_one_cli_argument(tmp_path):
    from research_pipeline.cli_args import build_parser
    dataset, reference = fixture(tmp_path)
    data = json.loads(reference.read_text())
    esbmc = ['/somewhere/esbmc', '--no-pointer-check', '--no-align-check']
    data['config']['esbmc_command'] = esbmc
    reference.write_text(json.dumps(data))
    prepared = prepare(reference, dataset, tmp_path / 'out')
    args = build_parser().parse_args(prepared['command'][2:])
    assert args.esbmc_command == esbmc
