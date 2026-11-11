"""Armazena propostas em quarentena; não aplica mudanças ao pipeline."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from research_pipeline.verify.lessons import approved_repairs, lesson_key

_KINDS = frozenset({'licao', 'regra_compat', 'issue', 'codigo'})
_STATUSES = frozenset({'quarentena', 'aceita', 'rejeitada'})
_ID = re.compile(r'[0-9a-f]{64}\Z')


def _present(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def add_proposal(kind: str, title: str, evidence: dict, root: Path, *, author: str) -> str:
    if kind not in _KINDS or not _present(title) or not _present(author) or not isinstance(evidence, dict):
        raise ValueError('Tipo, título, autor ou evidência inválidos')
    origin = evidence.get('origin')
    if (not _present(evidence.get('program')) or not isinstance(origin, dict)
            or not _present(origin.get('run')) or not _present(origin.get('case'))):
        raise ValueError('Informe programa, rodada e caso na evidência')
    key = None
    if kind == 'licao' and _present(evidence.get('error')) and _present(evidence.get('fix')):
        key = lesson_key(evidence['error'], evidence['fix'])
        if f'\n- Key: {key}\n' in '\n' + approved_repairs() + '\n':
            raise ValueError('Esta lição já aceita consta do caderno')
    payload = json.dumps({'kind': kind, 'evidence': evidence}, ensure_ascii=False, sort_keys=True,
                         separators=(',', ':'), allow_nan=False)
    proposal_id = hashlib.sha256(payload.encode('utf-8')).hexdigest()
    for existing in list_proposals(root):
        if existing['id'] == proposal_id or (key and existing.get('lesson_key') == key):
            return existing['id']
    directory = root / proposal_id
    directory.mkdir(parents=True, exist_ok=False)
    proposal = {'id': proposal_id, 'kind': kind, 'title': title, 'author': author,
                'evidence': evidence, 'status': 'quarentena', 'lesson_key': key}
    (directory / 'proposal.json').write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return proposal_id


def list_proposals(root: Path) -> list[dict]:
    if not root.exists():
        return []
    return [json.loads(path.read_text(encoding='utf-8')) for path in sorted(root.glob('*/proposal.json'))]


def set_status(root: Path, proposal_id: str, status: str, *, aprovada_por: str | None = None) -> None:
    if not _ID.fullmatch(proposal_id) or status not in _STATUSES:
        raise ValueError('Identificador ou estado inválido')
    path = root / proposal_id / 'proposal.json'
    proposal = json.loads(path.read_text(encoding='utf-8'))
    if proposal['kind'] == 'codigo' and status == 'aceita' and not _present(aprovada_por):
        raise ValueError('Proposta de código exige aprovação humana identificada')
    proposal['status'] = status
    if aprovada_por is not None:
        proposal['aprovada_por'] = aprovada_por
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def accept_by_gate(root: Path, proposal_id: str, gate: dict) -> None:
    """Registra aceitação automática somente após uma avaliação completa."""
    if not _ID.fullmatch(proposal_id) or gate.get('verdict') != 'ACEITA' or gate.get('reasons') != []:
        raise ValueError('Portão não aceitou a proposta')
    path = root / proposal_id / 'proposal.json'
    proposal = json.loads(path.read_text(encoding='utf-8'))
    if proposal['status'] != 'quarentena':
        raise ValueError('A proposta não está em quarentena')
    proposal['status'] = 'aceita'
    proposal['approval_method'] = 'portao_automatico'
    path.write_text(json.dumps(proposal, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
