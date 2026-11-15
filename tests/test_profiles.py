from __future__ import annotations

import pytest

from research_pipeline.cli_args import PROFILES, build_parser


def _parse(*flags: str):
    return build_parser().parse_args(["--mode", "hybrid", "--input", "x", *flags])


def test_no_profile_leaves_every_default() -> None:
    args = _parse()
    assert args.profile is None and args.auto_lessons is True and args.operational_retries == 0


def test_measurement_profile_turns_lessons_off_and_enables_operational_retries() -> None:
    args = _parse("--profile", "medicao")
    assert args.auto_lessons is False and args.operational_retries == 2 and args.workers == 1


def test_fast_profile_caps_repair() -> None:
    args = _parse("--profile", "rapido")
    assert args.heal_triage is True and args.heal_rounds == 1


def test_an_explicit_flag_wins_over_the_profile() -> None:
    assert _parse("--profile", "rapido", "--heal-rounds", "2").heal_rounds == 2
    assert _parse("--profile", "medicao", "--operational-retries", "5").operational_retries == 5


def test_profiles_only_name_existing_options() -> None:
    args = _parse()
    for settings in PROFILES.values():
        assert all(hasattr(args, dest) for dest in settings)


def test_unknown_profile_is_refused() -> None:
    with pytest.raises(SystemExit):
        _parse("--profile", "inventado")


def test_standard_profile_is_a_no_op_and_not_recorded_as_a_change() -> None:
    assert _parse("--profile", "padrao").auto_lessons is True


def test_frozen_profile_sets_experiment_defaults():
    args = _parse('--profile', 'congelado')
    assert args.claude_isolated is True
    assert args.auto_lessons is False
    assert args.operational_retries == 2
    assert args.workers == 1
    assert args.heal == 'error+kb'
    assert args.require_fresh_esbmc is True
    assert args.kb_content_cache is True
    assert args.evaluate_by_function is True


@pytest.mark.parametrize('profile', ['rapido', 'medicao', 'congelado'])
def test_explicit_default_value_also_wins(profile):
    args = _parse('--profile', profile, '--operational-retries=0', '--workers', '1', '--heal-rounds', '3')
    assert args.operational_retries == 0
    assert args.workers == 1
    assert args.heal_rounds == 3


def test_default_profile_keeps_new_options_off():
    for flags in ((), ('--profile', 'padrao')):
        args = _parse(*flags)
        assert args.require_fresh_esbmc is False
        assert args.kb_content_cache is False
        assert args.evaluate_by_function is False


def test_frozen_boolean_options_can_be_overridden():
    args = _parse('--profile', 'congelado', '--no-claude-isolated', '--no-kb-content-cache',
                  '--no-evaluate-by-function', '--heal', 'none', '--workers', '3')
    assert args.claude_isolated is False and args.kb_content_cache is False
    assert args.evaluate_by_function is False
    assert args.heal == 'none' and args.workers == 3


def test_no_profile_fingerprint_matches_previous_formula(tmp_path, monkeypatch):
    import json
    from hashlib import sha256
    from pathlib import Path
    import main
    from research_pipeline.llm.prompts import load_system_prompt
    from research_pipeline.llm.schema import v2_findings_schema
    from test_main_v2 import _run_config

    config, _, _ = _run_config(tmp_path, monkeypatch)
    assert not {'esbmc_provenance', 'kb_content_cache', 'evaluate_by_function', 'profile'} & config.keys()
    fingerprint = json.loads((tmp_path / 'out/v2_checkpoint.json').read_text())['fingerprint']
    variants = tuple(config['v2_variants'])
    expected = {'config': config,
        'sources': {str(Path(p).resolve()): sha256(Path(p).read_bytes()).hexdigest() for p in config['input_files']},
        'detector_prompt': sha256((main.REPO_ROOT / 'src/research_pipeline/prompts/system_prompt_v2.txt').read_bytes()).hexdigest(),
        'detector_schema': sha256(json.dumps(v2_findings_schema(variants), sort_keys=True).encode()).hexdigest(),
        'spec_prompt': sha256((main.REPO_ROOT / 'src/research_pipeline/prompts/input_spec_prompt.txt').read_bytes()).hexdigest()}
    if variants:
        expected['detector_system_prompt'] = sha256(load_system_prompt(
            include_smells=False, v2_detection=True, v2_variants=variants).encode()).hexdigest()
    assert fingerprint == expected


def test_frozen_profile_refuses_scan_before_planning(tmp_path, monkeypatch, capsys):
    import main
    args = build_parser().parse_args(['--mode', 'scan', '--profile', 'congelado', '--input', str(tmp_path)])
    monkeypatch.setattr(main, 'plan_scan', lambda *a, **kw: pytest.fail('must reject unsupported profile first'))
    assert main.mode_scan(args) == 1
    assert 'congelado' in capsys.readouterr().err


def test_function_metrics_include_review_dropped_in_real_cli_wiring(tmp_path, monkeypatch):
    import json
    import main
    from test_main_v2 import _run_config
    item = {'id': 'a', 'detection_file': 'sample.py', 'function': 'divide',
            'expression': 'x // y', 'categories': ['bug'], 'expected_type': 'ZeroDivisionError'}
    gt = tmp_path / 'ground_truths.json'
    gt.write_text(json.dumps({'items': [item]}))
    (tmp_path / 'manifest.json').write_text(json.dumps({'items': [item]}))
    monkeypatch.setattr(main, '_apply_review', lambda candidates, *a: (
        [], {'review_dropped': [c.to_dict() for c in candidates], 'review_errors': 0}))
    _run_config(tmp_path, monkeypatch, '--evaluate-by-function', '--review-threshold', '5',
                '--ground-truth', str(gt))
    report = json.loads((tmp_path / 'out/v2_verify_report.json').read_text())
    assert report['evaluation']['by_function']['apontado'] == 1
    assert report['evaluation']['by_function']['apontado_e_reproduzido'] is None
    assert report['evaluation']['detection']['tp'] == 0


def test_parse_known_args_works_with_a_profile():
    from research_pipeline.cli_args import build_parser

    parsed, rest = build_parser().parse_known_args(["--input", "x.py", "--profile", "congelado", "--extra"])
    assert parsed.profile == "congelado" and rest == ["--extra"]
