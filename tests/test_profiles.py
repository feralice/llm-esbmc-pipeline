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
