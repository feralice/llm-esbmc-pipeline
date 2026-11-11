"""Registra lições candidatas para avaliação, sem alterar o caderno ativo."""

from pathlib import Path

from .proposals import add_proposal, list_proposals


def queue_lesson(*, error: str, fix: str, program: str, case: str, run_dir: Path) -> bool:
    if not error.startswith('ERROR:') or not program.strip() or not fix.strip():
        raise ValueError('Lição exige diagnóstico, programa e alteração')
    root = Path(run_dir) / 'quarentena'
    evidence = {'program': program, 'origin': {'run': str(run_dir), 'case': case}, 'error': error, 'fix': fix}
    before = {item['id'] for item in list_proposals(root)}
    try:
        proposal_id = add_proposal('licao', error[:80], evidence, root, author='self-learning')
    except ValueError as exc:
        if 'lição já aceita' in str(exc):
            return False
        raise
    return proposal_id not in before


def promote_lesson(root: Path, proposals_root: Path, proposal_id: str, *, scratch: Path, evaluate) -> dict:
    """Prepara a lição numa cópia; só a aplica se a avaliação autorizar."""
    import difflib
    import tempfile
    from datetime import datetime

    from research_pipeline.verify.lessons import add_auto_lesson

    from .automatic import apply_proposal
    from .proposals import accept_by_gate

    matches = [p for p in list_proposals(proposals_root) if p['id'] == proposal_id]
    if len(matches) != 1 or matches[0]['kind'] != 'licao' or matches[0]['status'] != 'quarentena':
        raise ValueError('Proposta de lição em quarentena não encontrada')
    evidence = matches[0]['evidence']
    if not isinstance(evidence.get('error'), str) or not evidence['error'].startswith('ERROR:') or not isinstance(evidence.get('fix'), str) or not evidence['fix'].strip():
        raise ValueError('Lição exige erro e alteração para promoção')
    if scratch.resolve().is_relative_to(root.resolve()):
        raise ValueError('A pasta temporária deve ficar fora do repositório')
    scratch.mkdir(parents=True, exist_ok=True)
    relative = Path('src/research_pipeline/verify/skills/reparos-aprendidos/SKILL.md')
    original = (root / relative).read_text(encoding='utf-8')
    staged = Path(tempfile.mkdtemp(prefix='licao_', dir=scratch)) / 'SKILL.md'
    staged.write_text(original, encoding='utf-8')
    added = add_auto_lesson(error=evidence['error'], fix=evidence['fix'], reached='a verdict',
                            case=evidence['origin']['case'], run=evidence['origin']['run'],
                            today=datetime.now().astimezone().date(), path=staged)
    if not added:
        raise ValueError('Lição já está no caderno')
    patch = ''.join(difflib.unified_diff(original.splitlines(keepends=True),
                                         staged.read_text(encoding='utf-8').splitlines(keepends=True),
                                         fromfile=f'a/{relative}', tofile=f'b/{relative}')).encode('utf-8')
    result = apply_proposal(root, patch, scratch=scratch, evaluate=evaluate)
    if result['applied']:
        accept_by_gate(proposals_root, proposal_id, result['gate'])
    return result
