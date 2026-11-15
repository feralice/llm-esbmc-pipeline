import json
from pathlib import Path
import runpy

import pytest

from research_pipeline.scan.pipeline import summary_markdown
from research_pipeline.verify.run_report import render_run_report

NOTICE = 'confirmado no harness; a entrada usada pode não ser alcançável pelo código real; leia o código e reproduza fora do harness antes de reportar'


@pytest.mark.parametrize('verdict', ['CONFIRMED', 'NOT_CONFIRMED'])
def test_notice_in_three_reports_only_with_confirmed(tmp_path, verdict):
    result = {'hypothesis': {'file': str(tmp_path / 'a.py'), 'function': 'f',
                             'suspect_expression': 'x[0]', 'trigger_condition': 'empty'},
              'verdict': verdict, 'reason': ''}
    report = {'config': {'root': str(tmp_path)}, 'graph': {'functions': 1, 'modules': 1,
              'resolved_calls': 0, 'call_sites': 0}, 'detection': {'functions': 1, 'failed': 0,
              'hypotheses': 1, 'held': 0}, 'verification': {'by_verdict': {verdict: 1}},
              'levels': {'summary': {'by_level': {}}}, 'results': [result]}
    (tmp_path / 'scan_report.json').write_text(json.dumps(report))
    script = runpy.run_path(str(Path(__file__).resolve().parents[1] / 'scripts/relatorio_scans.py'))
    texts = [summary_markdown(report), render_run_report([result]), script['summarize']([tmp_path])]
    for text in texts:
        assert (NOTICE in text) == (verdict == 'CONFIRMED')
