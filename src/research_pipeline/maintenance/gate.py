"""Compara evidências de manutenção sem aplicar propostas automaticamente."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path


def run_gate(reference_report: Path, *, esbmc_command: list[str], runner: Callable | None = None,
             replay: Callable | None = None, suite: Callable | None = None, holdout: Path | None = None,
             baseline_probes: dict | None = None, baseline_failures: list[str] | None = None,
             baseline_passed: int | None = None) -> dict:
    reference = json.loads(reference_report.read_text(encoding='utf-8'))
    before = reference['evaluation']['confirmed_by_location']['location']['tp']
    replay_result = replay(reference_report) if replay else {}
    probe_result = runner() if runner else {}
    suite_result = suite() if suite else {}
    after = replay_result.get('confirmed')
    old_probes = (baseline_probes or {}).get('results', {})
    new_probes = probe_result.get('results', {})
    old_accepted = {k for k, v in old_probes.items() if v.get('outcome') == 'aceita'}
    new_accepted = {k for k, v in new_probes.items() if v.get('outcome') == 'aceita'}
    worse = sorted(old_accepted - new_accepted)
    failures = suite_result.get('failures')
    new_failures = sorted(set(failures) - set(baseline_failures)) if failures is not None and baseline_failures is not None else None
    metrics = {'bugs_confirmados': {'antes': before, 'depois': after},
               'sondas': {'antes': len(old_accepted) if old_probes else None,
                           'depois': len(new_accepted) if new_probes else None, 'pioraram': worse},
               'testes': {'antes': baseline_passed, 'depois': suite_result.get('passed'),
                          'falhas_anteriores': baseline_failures, 'falhas_atuais': failures,
                          'falhas_novas': new_failures}}
    reasons = []
    if not esbmc_command:
        reasons.append('Comando do ESBMC ausente')
    if not replay_result.get('complete') or not isinstance(after, int) or isinstance(after, bool):
        reasons.append('Replay incompleto ou sem contagem verificável')
    elif after < before:
        reasons.append('Bugs confirmados diminuíram')
    if (not old_probes or not new_probes or probe_result.get('reason') != 'sondas'
            or (baseline_probes or {}).get('reason') != 'sondas'
            or any(v.get('outcome') not in {'aceita', 'recusa'} for v in old_probes.values())
            or any(v.get('outcome') not in {'aceita', 'recusa'} for v in new_probes.values())
            or set(old_probes) != set(new_probes)):
        reasons.append('Sondas incompletas ou sem base comparável')
    old_identity = (baseline_probes or {}).get('identity')
    new_identity = probe_result.get('identity')
    if (old_identity or new_identity) and old_identity != new_identity:
        reasons.append('A identidade do ESBMC mudou entre as sondas')
    if worse:
        reasons.append('Sondas aceitas anteriormente pioraram')
    if (not suite_result.get('complete') or failures is None or baseline_failures is None
            or not isinstance(baseline_passed, int) or isinstance(baseline_passed, bool)
            or not isinstance(suite_result.get('passed'), int) or isinstance(suite_result.get('passed'), bool)):
        reasons.append('Testes incompletos ou sem base de falhas')
    elif new_failures:
        reasons.append('Há falhas novas na suíte')
    elif suite_result['passed'] < baseline_passed:
        reasons.append('Testes aprovados diminuíram')
    return {'verdict': 'REJEITADA' if reasons else 'ACEITA', 'metrics': metrics, 'reasons': reasons,
            'sample': 'dentro da amostra' if holdout is None else 'conjunto informado; independência não conferida'}


def recorded_replay(reference_report: Path, replay_dir: Path, ground_truth: Path) -> dict:
    """Valida a cobertura de um replay antes de contar os bugs pelo mesmo gabarito."""
    try:
        original = json.loads(reference_report.read_text(encoding='utf-8'))
        results = json.loads((replay_dir / 'report_0of1.json').read_text(encoding='utf-8'))['results']
        rows = json.loads((replay_dir / 'replay_specs_0of1.json').read_text(encoding='utf-8'))['rows']
    except (OSError, ValueError, KeyError):
        return {'complete': False, 'confirmed': None, 'reason': 'arquivos do replay ausentes ou inválidos'}
    original_ids = [row['hypothesis']['hypothesis_id'] for row in original['results']]
    replay_ids = [row['hypothesis']['hypothesis_id'] for row in results]
    row_ids = [row['id'] for row in rows]
    if (len(set(original_ids)) != len(original_ids) or sorted(original_ids) != sorted(replay_ids)
            or sorted(original_ids) != sorted(row_ids) or any(row.get('filled', 0) for row in rows)
            or any(row.get('verdict') == 'PIPELINE_ERROR' for row in results)):
        return {'complete': False, 'confirmed': None, 'reason': 'casos ausentes, duplicados, erros ou tipos preenchidos'}
    from research_pipeline.verify.report import _confirmed_by_location, _expected_items

    manifest = json.loads((ground_truth.parent / 'manifest.json').read_text(encoding='utf-8'))
    names = {Path(path).name for path in original['config']['input_files']}
    sources = [ground_truth.parent / item['detection_file'] for item in manifest['items']
               if Path(item['detection_file']).name in names]
    items, base = _expected_items(ground_truth, sources)
    files = {Path(item['detection_file']).name: str((base / item['detection_file']).resolve()) for item in items}
    normalized = [{**row, 'hypothesis': {**row['hypothesis'],
                   'file': files.get(Path(row['hypothesis']['file']).name, row['hypothesis']['file'])}}
                  for row in results]
    count = _confirmed_by_location(normalized, 'CONFIRMED', items, base)['location']['tp']
    return {'complete': True, 'confirmed': count}


def read_junit(path: Path, *, returncode: int) -> dict:
    """Lê a suíte concluída; erro interno ou timeout não viram sucesso."""
    import xml.etree.ElementTree as ET

    if returncode not in (0, 1):
        return {'complete': False, 'failures': None, 'passed': None}
    try:
        cases = ET.parse(path).getroot().findall('.//testcase')
    except (OSError, ET.ParseError):
        return {'complete': False, 'failures': None, 'passed': None}
    if not cases:
        return {'complete': False, 'failures': None, 'passed': None}
    failures = sorted(f"{case.get('classname', '')}::{case.get('name', '')}" for case in cases
                      if case.find('failure') is not None or case.find('error') is not None)
    skipped = sum(case.find('skipped') is not None for case in cases)
    if (returncode == 0 and failures) or (returncode == 1 and not failures):
        return {'complete': False, 'failures': None, 'passed': None}
    return {'complete': True, 'failures': failures, 'passed': len(cases) - len(failures) - skipped}
