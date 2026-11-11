from research_pipeline.verify.lessons import round_repairs


def _round(case, number, source, output):
    folder = case / "rounds" / f"{number:03d}"
    folder.mkdir(parents=True)
    (folder / "input.py").write_text(source)
    (folder / "output.txt").write_text(output)
    (folder / "exit_code").write_text("1")


def test_version_query_is_not_a_failed_harness_or_a_repair(tmp_path):
    _round(tmp_path, 1, "", "ESBMC version 8.6.0\n")
    _round(tmp_path, 2, "print(1)\n", "VERIFICATION SUCCESSFUL\n")
    assert round_repairs(tmp_path, {"verdict": "CONFIRMED"}) == []


def test_refusal_requires_error_and_both_programs(tmp_path):
    _round(tmp_path, 1, "print(0)\n", "ESBMC version 8.6.0\n")
    _round(tmp_path, 2, "print(1)\n", "VERIFICATION SUCCESSFUL\n")
    assert round_repairs(tmp_path, {"verdict": "CONFIRMED"}) == []


def test_actual_diagnostic_and_changed_harness_are_kept(tmp_path):
    _round(tmp_path, 1, "print(0)\n", "ERROR: unsupported\n")
    _round(tmp_path, 2, "print(1)\n", "VERIFICATION SUCCESSFUL\n")
    repairs = round_repairs(tmp_path, {"verdict": "CONFIRMED"})
    assert len(repairs) == 1 and repairs[0]["erro"] == "ERROR: unsupported"


def test_unchanged_program_is_not_a_repair(tmp_path):
    _round(tmp_path, 1, "print(1)\n", "ERROR: unsupported\n")
    _round(tmp_path, 2, "print(1)\n", "VERIFICATION SUCCESSFUL\n")
    assert round_repairs(tmp_path, {"verdict": "CONFIRMED"}) == []


def test_missing_result_program_is_not_a_repair(tmp_path):
    _round(tmp_path, 1, "print(0)\n", "ERROR: unsupported\n")
    _round(tmp_path, 2, "", "VERIFICATION SUCCESSFUL\n")
    assert round_repairs(tmp_path, {"verdict": "CONFIRMED"}) == []
