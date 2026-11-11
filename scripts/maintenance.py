"""Comando local de manutenção, sem chamadas de LLM."""

from __future__ import annotations

import argparse
import fcntl
import json
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

from research_pipeline.maintenance.execution import (
    prepare_baseline,
    process_code,
    process_lesson,
)
from research_pipeline.maintenance.fingerprint import pipeline_fingerprint
from research_pipeline.maintenance.gate import recorded_replay, run_gate
from research_pipeline.maintenance.limits import (
    compare_baseline,
    run_limits,
)
from research_pipeline.maintenance.proposals import (
    add_proposal,
    list_proposals,
    set_status,
)
from research_pipeline.maintenance.refusals import triage
from research_pipeline.maintenance.timing import (
    collect_timings,
    summarize,
)


def _search_issues(query: str) -> list[dict]:
    proc = subprocess.run(['gh', 'issue', 'list', '--repo', 'esbmc/esbmc', '--state', 'all', '--search', query,
                           '--json', 'number,title,url,state'], capture_output=True, text=True, timeout=30, check=True)
    return json.loads(proc.stdout)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Manutenção local, sem LLM')
    parser.add_argument('--output-dir', type=Path, default=Path('/mnt/e') / f'manutencao_{datetime.now().astimezone().date().isoformat()}')
    parser.add_argument('--esbmc', default=str(Path.home() / 'esbmc-master/build-bw/src/esbmc/esbmc'))
    parser.add_argument('--esbmc-arg', action='append', default=[])
    commands = parser.add_subparsers(dest='command', required=True)
    limit = commands.add_parser('limits')
    limit.add_argument('--timeout', type=int, default=300)
    refusal = commands.add_parser('refusals')
    refusal.add_argument('reports', nargs='+', type=Path)
    refusal.add_argument('--buscar-issues', action='store_true')
    timing = commands.add_parser('timing')
    timing.add_argument('reports', nargs='+', type=Path)
    proposals = commands.add_parser('proposals')
    proposals.add_argument('--root', type=Path, default=ROOT / 'src/research_pipeline/maintenance/quarentena')
    actions = proposals.add_subparsers(dest='action', required=True)
    add = actions.add_parser('add')
    add.add_argument('--kind', required=True, choices=['licao', 'regra_compat', 'issue', 'codigo'])
    add.add_argument('--title', required=True)
    add.add_argument('--author', required=True)
    add.add_argument('--evidence', required=True, type=Path)
    actions.add_parser('list')
    status = actions.add_parser('status')
    status.add_argument('id')
    status.add_argument('status', choices=['quarentena', 'aceita', 'rejeitada'])
    status.add_argument('--aprovada-por')
    baseline = commands.add_parser('baseline')
    baseline.add_argument('--reference', type=Path, default=ROOT / 'artifacts/pgene601/rodada-final-2026-11-09/v2_verify_report.json')
    auto = commands.add_parser('auto')
    auto.add_argument('queues', nargs='+', type=Path)
    auto.add_argument('--reference', type=Path, default=ROOT / 'artifacts/pgene601/rodada-final-2026-11-09/v2_verify_report.json')
    gate = commands.add_parser('gate')
    gate.add_argument('report', type=Path)
    gate.add_argument('--replay-dir', type=Path)
    gate.add_argument('--suite-evidence', type=Path)
    gate.add_argument('--baseline-suite', type=Path)
    gate.add_argument('--ground-truth', type=Path, default=ROOT / 'dataset/disciplina_pgene601/ground_truths.json')
    gate.add_argument('--holdout', type=Path)
    return parser


def _write_report(output: Path, name: str, fingerprint: dict, data: dict) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    index = 1
    while True:
        stem = name if index == 1 else f'{name}_{index}'
        json_path, md_path = output / f'{stem}.json', output / f'{stem}.md'
        if not json_path.exists() and not md_path.exists():
            break
        index += 1
    payload = {'fingerprint': fingerprint, 'resultado': data}
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tree = 'há alterações não commitadas' if fingerprint['dirty'] else 'sem alterações não commitadas'
    md_path.write_text('# Impressão digital\n\n' + f"Commit: `{fingerprint['git_commit']}`; {tree}.\n\n"
                       + '```json\n' + json.dumps(fingerprint, ensure_ascii=False, indent=2) + '\n```\n\n'
                       + '# Resultado\n\n```json\n' + json.dumps(data, ensure_ascii=False, indent=2)
                       + '\n```\n', encoding='utf-8')
    return json_path, md_path


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    esbmc_command = [args.esbmc, *args.esbmc_arg]
    previous_tmp = tempfile.tempdir
    try:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        tempfile.tempdir = str(args.output_dir.resolve())
        fingerprint = pipeline_fingerprint(ROOT, esbmc_command=esbmc_command,
                                           cache_dir=args.output_dir / 'cache_esbmc')
        if args.command == 'limits':
            outcomes = run_limits(esbmc_command, ROOT / 'docs/projeto/possiveis_problemas', timeout_seconds=args.timeout)
            baseline = compare_baseline(ROOT / 'docs/projeto/possiveis_problemas/baseline.json', outcomes,
                                        identity=fingerprint['esbmc_identity'])
            data = {'comparacao': baseline, 'outcomes': outcomes}
        elif args.command == 'refusals':
            registry = json.loads((ROOT / 'src/research_pipeline/maintenance/registry.json').read_text())
            data = triage(args.reports, registry, search=_search_issues if args.buscar_issues else None)
            data['busca_issues'] = 'possíveis issues existentes' if args.buscar_issues else 'não realizada'
        elif args.command == 'timing':
            rows = collect_timings(args.reports)
            data = {'resumo': summarize(rows), 'registros': rows}
        elif args.command == 'baseline':
            job = Path(tempfile.mkdtemp(prefix='base_', dir=args.output_dir))
            data = prepare_baseline(ROOT, args.reference, job, esbmc_command)
        elif args.command == 'auto':
            args.output_dir.mkdir(parents=True, exist_ok=True)
            decisions = []
            halted = False
            for queue in args.queues:
                if halted:
                    break
                if not queue.is_dir():
                    decisions.append({'fila': str(queue), 'resultado': {'applied': False, 'reason': 'fila não encontrada'}})
                    continue
                with (queue / '.maintenance.lock').open('a', encoding='utf-8') as lock:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    except BlockingIOError:
                        decisions.append({'fila': str(queue), 'resultado': {'applied': False, 'reason': 'fila já está em avaliação'}})
                        continue
                    for proposal in list_proposals(queue):
                        if proposal['status'] != 'quarentena':
                            continue
                        if proposal['kind'] not in {'licao', 'codigo'}:
                            decisions.append({'id': proposal['id'], 'resultado': {'applied': False, 'reason': 'tipo ainda não automatizado'}})
                            continue
                        job = Path(tempfile.mkdtemp(prefix='avaliacao_', dir=args.output_dir))
                        processor = process_lesson if proposal['kind'] == 'licao' else process_code
                        try:
                            decision = processor(ROOT, queue, proposal['id'], args.reference, job, esbmc_command)
                        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                            decision = {'applied': False, 'ready': False, 'reason': f'falha na avaliação: {exc}'}
                        decisions.append({'id': proposal['id'], 'resultado': decision})
                        if decision.get('ready') is False:
                            halted = True
                            break
            data = {'propostas': decisions}
        elif args.command == 'gate':
            reference = json.loads(args.report.read_text(encoding='utf-8'))
            suite = json.loads(args.suite_evidence.read_text(encoding='utf-8')) if args.suite_evidence else {}
            baseline = json.loads(args.baseline_suite.read_text(encoding='utf-8')) if args.baseline_suite else {}
            replay = (lambda path: recorded_replay(path, args.replay_dir, args.ground_truth)) if args.replay_dir else None
            data = run_gate(args.report, esbmc_command=esbmc_command, runner=lambda: fingerprint['rules'],
                            replay=replay, suite=lambda: suite, baseline_failures=baseline.get('failures'),
                            baseline_probes=reference.get('config', {}).get('capabilities'), holdout=args.holdout,
                            baseline_passed=baseline.get('passed'))
        else:
            if args.action == 'add':
                evidence = json.loads(args.evidence.read_text(encoding='utf-8'))
                proposal_id = add_proposal(args.kind, args.title, evidence, args.root, author=args.author)
                proposal = next(item for item in list_proposals(args.root) if item['id'] == proposal_id)
                data = {'id': proposal_id, 'status': proposal['status']}
            elif args.action == 'status':
                set_status(args.root, args.id, args.status, aprovada_por=args.aprovada_por)
                data = {'id': args.id, 'status': args.status, 'aplicada': False}
            else:
                data = {'propostas': list_proposals(args.root)}
        paths = _write_report(args.output_dir, args.command, fingerprint, data)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f'Erro: {exc}', file=sys.stderr)
        return 1
    finally:
        tempfile.tempdir = previous_tmp
    print(f'Relatórios: {paths[0]} e {paths[1]}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
