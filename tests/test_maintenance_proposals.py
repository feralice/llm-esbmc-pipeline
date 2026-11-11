import pytest

from research_pipeline.maintenance.proposals import (
    add_proposal,
    list_proposals,
    set_status,
)


@pytest.fixture
def evidence():
    return {'program': 'assert False', 'origin': {'run': 'rodada', 'case': 'caso'}}


def test_proposal_without_program_or_origin_is_refused(tmp_path, evidence):
    for data in ({'origin': evidence['origin']}, {'program': evidence['program']},
                 {'program': evidence['program'], 'origin': {'run': 'r'}}):
        with pytest.raises(ValueError):
            add_proposal('issue', 'Título', data, tmp_path, author='Fernanda')
    assert not list(tmp_path.iterdir())


def test_code_proposal_cannot_be_accepted_without_a_human_approval(tmp_path, evidence):
    proposal_id = add_proposal('codigo', 'Título', evidence, tmp_path, author='IA')
    with pytest.raises(ValueError):
        set_status(tmp_path, proposal_id, 'aceita')
    assert list_proposals(tmp_path)[0]['status'] == 'quarentena'
    set_status(tmp_path, proposal_id, 'aceita', aprovada_por='Fernanda')
    proposal, = list_proposals(tmp_path)
    assert proposal['status'] == 'aceita'
    assert proposal['aprovada_por'] == 'Fernanda'


def test_duplicate_proposal_by_evidence_hash_is_not_added_twice(tmp_path, evidence):
    first = add_proposal('issue', 'Um título', evidence, tmp_path, author='IA')
    second = add_proposal('issue', 'Outro título', evidence, tmp_path, author='Fernanda')
    assert first == second
    assert len(list_proposals(tmp_path)) == 1


def test_existing_approved_lesson_is_not_duplicated(tmp_path, evidence, monkeypatch):
    from research_pipeline.verify.lessons import lesson_key

    evidence.update(error='ERROR: example', fix='+ replacement')
    key = lesson_key(evidence['error'], evidence['fix'])
    monkeypatch.setattr('research_pipeline.maintenance.proposals.approved_repairs', lambda: f'### repair\n- Key: {key}\n')
    with pytest.raises(ValueError, match='lição já aceita'):
        add_proposal('licao', 'Título', evidence, tmp_path, author='IA')
    assert not list(tmp_path.iterdir())


def test_invalid_id_and_invalid_kind_cannot_write_outside_quarantine(tmp_path, evidence):
    with pytest.raises(ValueError):
        set_status(tmp_path, '../outside', 'aceita')
    with pytest.raises(ValueError):
        add_proposal('desconhecido', 'Título', evidence, tmp_path, author='IA')
