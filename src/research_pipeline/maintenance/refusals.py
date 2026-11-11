"""Agrupa recusas registradas, sem executar LLM ou publicar resultados."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from research_pipeline.verify.levels import CONTEXT, CRASH, LANGUAGE, limit_group
from research_pipeline.verify.outcome import CHECKED

_PATH = re.compile(r'(?:[A-Za-z]:)?(?:/|\\)[^\s\'"`]+')
_HYPOTHESIS = re.compile(r'\b[0-9a-f]{12}(?:_a\d+)?\b', re.IGNORECASE)
_LINE = re.compile(r'(?<=\s)\d+(?=\s*:)')
_USER_NAME = re.compile(r"\b(variable|argument|parameter)\s+['\"`][^'\"`]+['\"`]", re.IGNORECASE)


def normalize_reason(reason: str) -> str:
    reason = _PATH.sub('<caminho>', reason)
    reason = _HYPOTHESIS.sub('<hipotese>', reason)
    reason = _LINE.sub('<linha>', reason)
    reason = _USER_NAME.sub(r'\1 <nome>', reason)
    return ' '.join(reason.split())


def triage(reports: list[Path], registry: dict[str, dict],
           search: Callable[[str], list[dict]] | None = None) -> dict:
    groups: dict[tuple[str, str], dict] = {}
    for path in reports:
        report = json.loads(path.read_text(encoding='utf-8'))
        model = report.get('config', {}).get('model') or f'modelo não informado ({path})'
        for result in report.get('results', []):
            verdict = result.get('verdict', '')
            reason = result.get('reason', '')
            if verdict in CHECKED:
                continue
            group = limit_group(verdict, reason)
            explicit = (verdict in {'LLM_ONLY', 'UNSUPPORTED'} and 'ERROR:' in reason
                        and ('UNSUPPORTED:' in reason or 'not supported' in reason.lower()))
            if group not in {LANGUAGE, CONTEXT, CRASH} and not explicit:
                continue
            signature = normalize_reason(reason)
            key = (model, signature)
            entry = groups.setdefault(key, {'signature': signature, 'model': model, 'count': 0, 'occurrences': []})
            hypothesis = result.get('hypothesis', {})
            entry['count'] += 1
            entry['occurrences'].append({'function': hypothesis.get('function', ''),
                                         'file': hypothesis.get('file', ''),
                                         'program': result.get('program_path', ''), 'report': str(path)})
    known, new = [], []
    searches: dict[str, list[dict]] = {}
    for (_, signature), entry in sorted(groups.items()):
        if signature in registry:
            entry['registry'] = registry[signature]
            known.append(entry)
        else:
            if search is not None and signature not in searches:
                searches[signature] = search(signature)
            entry['possible_issues'] = searches.get(signature, [])
            new.append(entry)
    by_model: dict[str, dict] = {}
    for label, entries in (('known', known), ('new', new)):
        for entry in entries:
            by_model.setdefault(entry['model'], {'known': [], 'new': []})[label].append(entry)
    return {'known': known, 'new': new, 'by_model': by_model}
