"""Prepare matched fixed-function inputs. Detection runs only with explicit --execute."""

from __future__ import annotations

import argparse
import ast
import json
import os
import shlex
import subprocess
import sys
from datetime import datetime
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from build_disciplina_pgene601 import _excerpt, _one_function  # noqa: E402
from research_pipeline.preprocess import preprocess_file  # noqa: E402


def prepare(reference: Path, dataset: Path, output: Path) -> dict:
    config = json.loads(reference.read_text(encoding='utf-8'))['config']
    if config.get('profile') != 'congelado':
        raise ValueError('A referência precisa usar o perfil congelado, como a nova rodada dos 47.')
    if not config.get('model') or not config.get('backend') or not config.get('v2_variants'):
        raise ValueError('A referência precisa informar modelo, backend e variantes explícitos.')
    if config.get('routing') or config.get('review_threshold') is not None:
        raise ValueError('Referência com roteamento automático ou revisão adicional não é suportada neste controle.')
    if output.exists():
        raise ValueError('A pasta de saída já existe; use outra para preservar os resultados.')
    paths = config.get('input_files') or []
    if not paths:
        raise ValueError('A referência não informa os arquivos de entrada.')
    excerpts, hashes, function_count = {}, {}, 0
    for file in sorted(paths):
        buggy = dataset / 'funcao_com_bug' / Path(file).name
        if Path(file).resolve() != buggy.resolve():
            raise ValueError(f'A referência não usa o recorte esperado: {file}')
        fixed = dataset / 'arquivo_corrigido' / buggy.name
        names = [u.qualname for u in preprocess_file(buggy) if u.kind == 'function']
        if not names:
            raise ValueError(f'Recorte sem funções: {buggy}')
        try:
            fixed_source = fixed.read_text(encoding='utf-8')
            tree = ast.parse(fixed_source)
            missing = [name for name in names if _one_function(tree, name) is None]
            if missing:
                raise ValueError('Funções ausentes: ' + ', '.join(missing))
            excerpt = _excerpt(fixed_source, ' / '.join(names))
        except (OSError, ValueError, SyntaxError) as exc:
            raise ValueError(f'Não foi possível recortar {buggy.name}: {", ".join(names)}') from exc
        excerpts[buggy.name] = excerpt
        function_count += len(names)
        hashes[buggy.name] = {'buggy_crop': sha256(buggy.read_bytes()).hexdigest(),
                             'fixed_full': sha256(fixed.read_bytes()).hexdigest(),
                             'fixed_crop': sha256(excerpt.encode()).hexdigest(), 'functions': names}
    command = [sys.executable, str(ROOT / 'src/main.py'), '--mode', 'hybrid', '--profile', 'congelado',
               '--v2-stage', 'detection', '--input', str(output / 'funcao_corrigida'),
               '--backend', config['backend'], '--model', config['model'],
               '--v2-variants', ','.join(config['v2_variants']), '--output-dir', str(output / 'run')]
    if config.get('esbmc_command'):
        command += ['--esbmc-command', shlex.join(config['esbmc_command'])]
    if not config.get('claude_isolated'):
        command += ['--no-claude-isolated']
    if config.get('context_sources'):
        command += ['--context-sources', str(dataset / 'arquivo_corrigido')]
    for option in ('example_pool', 'example_k', 'max_hypotheses_per_function', 'llm_timeout'):
        if config.get(option) is not None:
            command += ['--' + option.replace('_', '-'), str(config[option])]
    commit = subprocess.check_output(['git', '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    data = {'reference_report': str(reference), 'reference_sha256': sha256(reference.read_bytes()).hexdigest(),
            'pipeline_commit': commit, 'command': command, 'files': len(excerpts),
            'estimated_calls': function_count, 'estimated_tokens_53_functions': 80000,
            'estimated_tokens': round(80000 * function_count / 53),
            'estimate_note': 'Estimativa inicial do plano; não é medição, não contabiliza cache e exclui retentativas.',
            'control_note': 'Versões corrigidas dos casos rotulados, sem garantia de ausência de outros bugs.',
            'source_hashes': hashes}
    (output / 'funcao_corrigida').mkdir(parents=True)
    for name, source in excerpts.items():
        (output / 'funcao_corrigida' / name).write_text(source, encoding='utf-8')
    (output / 'commit.txt').write_text(commit + '\n', encoding='utf-8')
    (output / 'preparacao.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--dataset', type=Path, default=ROOT / 'dataset/disciplina_pgene601')
    parser.add_argument('--output-dir', type=Path, default=None)
    parser.add_argument('--execute', action='store_true', help='Inicia chamadas à LLM; exige autorização prévia.')
    args = parser.parse_args()
    output = (args.output_dir or ROOT / 'artifacts/pgene601' /
              ('deteccao-corrigidas-' + datetime.now().strftime('%Y-%m-%d-%H%M%S'))).resolve()
    try:
        data = prepare(args.reference.resolve(), args.dataset.resolve(), output)
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f'Erro ao preparar: {exc}', file=sys.stderr)
        return 1
    print(f"Preparados {data['files']} arquivos, {data['estimated_calls']} chamadas estimadas; "
          f"~{data['estimated_tokens']} tokens, sem contabilizar cache. Metadados: {output / 'preparacao.json'}", flush=True)
    if not args.execute:
        print('Somente preparação. Nenhuma chamada à LLM foi feita.')
        return 0
    return subprocess.run(data['command'], cwd=ROOT,
                          env={**os.environ, 'PYTHONPATH': str(ROOT / 'src')}, check=False).returncode


if __name__ == '__main__':
    raise SystemExit(main())
