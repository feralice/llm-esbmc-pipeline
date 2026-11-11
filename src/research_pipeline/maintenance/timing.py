"""Reúne tempos e limites registrados, sem alterar a configuração do pipeline."""

from __future__ import annotations

import json
from pathlib import Path


def collect_timings(reports: list[Path]) -> list[dict]:
    rows = []
    for path in reports:
        report = json.loads(path.read_text(encoding='utf-8'))
        model = report.get('config', {}).get('model') or None
        for result in report.get('results', []):
            attempts = result.get('attempts') or [{}]
            for attempt in attempts:
                bound = attempt.get('unwind')
                if not isinstance(bound, int) or isinstance(bound, bool) or bound <= 0:
                    bound = None
                rows.append({'function': result.get('hypothesis', {}).get('function', ''),
                             'bound': bound, 'seconds': attempt.get('seconds'),
                             'hypothesis_seconds': result.get('seconds'),
                             'verdict': result.get('verdict'), 'attempt_status': attempt.get('esbmc_status'),
                             'model': model, 'report': str(path)})
    return rows


def summarize(rows: list[dict]) -> dict:
    by_bound = {}
    for row in rows:
        bound = row.get('bound')
        if bound is None:
            continue
        entry = by_bound.setdefault(bound, {'attempts': 0, 'timeouts': 0, 'measured_statuses': 0,
                                            'missing_status': 0})
        entry['attempts'] += 1
        status = row.get('attempt_status')
        if not status or status == 'skipped':
            entry['missing_status'] += 1
        else:
            entry['measured_statuses'] += 1
            entry['timeouts'] += status == 'timeout'
    for entry in by_bound.values():
        denominator = entry['measured_statuses']
        entry['timeout_rate'] = entry['timeouts'] / denominator if denominator else None
    return {'missing_bound': sum(row.get('bound') is None for row in rows),
            'missing_seconds': sum(row.get('seconds') is None for row in rows), 'by_bound': by_bound}
