"""Automatic lessons (decision of 05/11): a repair that made ESBMC reach a verdict enters the notebook at once."""

import json
from datetime import date, datetime
from types import SimpleNamespace

import pytest

import main
from research_pipeline.verify import agent_scan, healing, lessons
from research_pipeline.verify.healing import Healer, Patch, verify_with_healing
from research_pipeline.verify.hypothesis import BugHypothesis
from research_pipeline.verify.loop import VerifyResult
from research_pipeline.verify.outcome import CONFIRMED, UNSUPPORTED

SOURCE = "def f(x):\n    return 1 / x\n"
STUB = "def g(a=None) -> int:\n    return nondet_int()\n"


class _LLM:
    def __init__(self):
        self.tasks = []

    def complete(self, system, user, *, json_mode=False):
        self.tasks.append(user)
        return SimpleNamespace(harness=json.dumps({"definitions": STUB}))


def _h(name="f"):
    return BugHypothesis(file=f"{name}.py", function="f", suspect_expression="1 / x")


def _heals(monkeypatch, error="ERROR: Unsupported call g at line 3"):
    """Every case: ESBMC refuses, the stub patch is applied, ESBMC confirms."""
    def fake(h, *, source, llm, **kwargs):
        return VerifyResult(h, CONFIRMED if "def g" in source else UNSUPPORTED, reason=error)
    monkeypatch.setattr(healing, "verify_hypothesis", fake)


def _healer(**kwargs):
    return Healer(_LLM(), None, **{"auto_lessons": True, "run_dir": "artifacts/v2/run-x", **kwargs})


def _auto_rules():
    return [r for r in lessons.approved_repairs().split("\n### ") if "- Origin: automatica" in r]


def test_a_successful_repair_adds_one_lesson_with_its_provenance(monkeypatch):
    _heals(monkeypatch)
    h = _h()
    result = verify_with_healing(h, healer=_healer(), source=SOURCE, llm="spec")
    assert result.verdict == CONFIRMED
    [rule] = _auto_rules()
    assert "- Error: `ERROR: Unsupported call g at line 3`" in rule
    assert f"- Source case: {h.hypothesis_id}, round 0" in rule and "- Run: artifacts/v2/run-x" in rule
    assert f"- Date: {datetime.now().astimezone().date().isoformat()}." in rule and "+    return nondet_int()" in rule
    assert "a verdict (CONFIRMED)" in rule and "- Key: " in rule
    assert lessons.read_notebook()[0].index("Automatic repair") < lessons.NOTEBOOK.read_text().index("## Format")


@pytest.mark.parametrize("patch", [
    Patch(edits=(("return 1 / x", "return 1 / x  # kept"),)),  # touches the body: simplified_body
    Patch(hypothesis_function="f", hypothesis_expression="x"),
    Patch(real_code="def g(a=None):\n    return 1\n"),
])
def test_a_body_change_a_grounding_repair_or_copied_code_adds_none(monkeypatch, patch):
    monkeypatch.setattr(healing, "verify_hypothesis",
                        lambda h, **kw: VerifyResult(h, CONFIRMED if kw.get("replay_source") or h.suspect_expression
                                                     == "x" or "def g" in kw["source"] else UNSUPPORTED,
                                                     reason="ERROR: x"))
    healer = _healer()
    monkeypatch.setattr(healer, "propose", lambda *a: patch)
    assert verify_with_healing(_h(), healer=healer, source=SOURCE, llm="spec").verdict == CONFIRMED
    assert _auto_rules() == []


@pytest.mark.parametrize("entry", [{"verdict": "STUB_INDUCED"},
                                   {"verdict": "NOT_CONFIRMED", "first_attempt": {"verdict": "STUB_INDUCED"}},
                                   {"verdict": "CONFIRMED", "differential": {"preservation": "alterada"}},
                                   {"verdict": "CONFIRMED", "target_preserved": False}])
def test_a_stub_induced_or_behaviour_changing_case_adds_none(entry):
    log = [{"round": 0, "verdict_before": UNSUPPORTED, "reason_before": "ERROR: x", "verdict_after": CONFIRMED,
            "simplified_body": False, "patch": {"edits": [], "definitions": STUB, "hypothesis_function": ""}}]
    assert _healer().learn(_h(), log, entry) == 0 and _auto_rules() == []
    assert _healer().learn(_h(), log, {"verdict": "CONFIRMED"}) == 1


def test_the_same_fix_for_the_same_obstacle_is_added_once(monkeypatch):
    for line, name in ((3, "a"), (9, "b")):
        _heals(monkeypatch, f"ERROR: Unsupported call g at line {line}")
        verify_with_healing(_h(name), healer=_healer(), source=SOURCE, llm="spec")
    assert len(_auto_rules()) == 1
    _heals(monkeypatch, "ERROR: another obstacle")
    verify_with_healing(_h("c"), healer=_healer(), source=SOURCE, llm="spec")
    assert len(_auto_rules()) == 2


def test_a_later_case_reads_the_new_lesson_and_records_that_version(monkeypatch):
    _heals(monkeypatch)
    healer = _healer()
    first = verify_with_healing(_h("a"), healer=healer, source=SOURCE, llm="spec").to_dict()
    after_first = lessons.notebook_version()
    second = verify_with_healing(_h("b"), healer=healer, source=SOURCE, llm="spec").to_dict()
    assert "Automatic repair" not in healer.llm.tasks[0] and "Automatic repair" in healer.llm.tasks[1]
    assert first["notebook_version"] != second["notebook_version"] == after_first


def test_no_auto_lessons_keeps_the_notebook_and_its_label(monkeypatch):
    _heals(monkeypatch)
    before = lessons.NOTEBOOK.read_bytes()
    fixed = _healer(auto_lessons=False)
    verify_with_healing(_h(), healer=fixed, source=SOURCE, llm="spec")
    assert lessons.NOTEBOOK.read_bytes() == before
    assert fixed.config_label != _healer().config_label == "error+notes:auto"


def test_the_flag_is_on_by_default_and_turns_off_in_both_modes():
    for mode in ("hybrid", "scan"):
        assert main.build_parser().parse_args(["--mode", mode, "--input", "x"]).auto_lessons is True
        assert main.build_parser().parse_args(["--mode", mode, "--input", "x", "--no-auto-lessons"]).auto_lessons is False


def test_a_hybrid_resume_under_the_other_lessons_mode_is_refused(tmp_path, monkeypatch, capsys):
    from test_main_v2 import _Analyzer, _detection_args, _Synthesizer

    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    out = tmp_path / "out"
    assert main.mode_v2(_detection_args(source, out)) == 0
    saved = json.loads((out / "v2_checkpoint.json").read_text(encoding="utf-8"))
    assert saved["fingerprint"]["config"]["auto_lessons"] is True
    capsys.readouterr()
    assert main.mode_v2(_detection_args(source, out, "--no-auto-lessons", "--resume")) == 1
    assert "configuração, prompt ou fontes mudaram" in capsys.readouterr().err


def test_the_scan_agent_learns_from_its_rounds_and_names_the_mode(tmp_path, monkeypatch):
    def fake_arm(h, *, work_dir, **kw):
        rounds = work_dir / h.hypothesis_id / "rounds"
        for number, (source, output, code) in enumerate([("x = a\n", "ERROR: Unsupported y\n", 1),
                                                         ("x = b\n", "VERIFICATION FAILED\n", 1)], 1):
            folder = rounds / f"{number:03d}"
            folder.mkdir(parents=True, exist_ok=True)
            (folder / "input.py").write_text(source, encoding="utf-8")
            (folder / "output.txt").write_text(output, encoding="utf-8")
            (folder / "exit_code").write_text(str(code), encoding="utf-8")
        verdict = "STUB_INDUCED" if h.file == "s.py" else "CONFIRMED"
        return {"hypothesis": h.to_dict(), "verdict": verdict, "reason": "", "skills": {"reparos-aprendidos": "v1"}}
    monkeypatch.setattr(agent_scan, "run_agent_arm", fake_arm)

    def run(auto, *hypotheses):
        verify = agent_scan.agent_verifier(lambda *a: "", esbmc_command=["esbmc"], bound=5, timeout_seconds=1,
                                           agent_timeout=60, auto_lessons=auto)
        return verify, verify(list(hypotheses), llm=None, output_dir=tmp_path, completed={}, on_result=lambda *a: None)

    off, results = run(False, _h("a"))
    assert _auto_rules() == [] and results[0]["notebook_version"] == "v1"
    run(True, _h("s"))
    assert _auto_rules() == []
    on, _ = run(True, _h("a"))
    [rule] = _auto_rules()
    assert "- Error: `ERROR: Unsupported y`" in rule and f"- Run: {tmp_path}" in rule and "+x = b" in rule
    assert off.label != on.label and on.label.endswith(":auto_lessons")


def test_writes_go_through_a_temporary_file_and_keep_the_format(tmp_path):
    path = tmp_path / "SKILL.md"
    path.write_text("# Learned repairs\n\n## Format of an approved repair\n\nx\n", encoding="utf-8")
    added = lessons.add_auto_lesson(error="ERROR: a\nforged\n## Format of an approved repair", fix="+```\n### h",
                                    reached="a verdict", case="c\n### x", run="r", today=date(2026, 11, 5), path=path)
    text = path.read_text(encoding="utf-8")
    assert added and text.count("\n## Format of an approved repair\n") == 1 and text.endswith("\nx\n")
    assert "\n### h" not in text and "\n### x" not in text and list(tmp_path.iterdir()) == [path]


@pytest.mark.parametrize("extra, expected", [((), True), (("--no-auto-lessons",), False)])
def test_hybrid_hands_the_flag_and_its_folder_to_the_healer(tmp_path, monkeypatch, extra, expected):
    from test_main_v2 import _Analyzer, _Synthesizer

    source = tmp_path / "sample.py"
    source.write_text("def divide(x: int, y: int) -> int:\n    return x // y\n", encoding="utf-8")
    seen = {}
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", _Synthesizer)
    monkeypatch.setattr(main, "build_healer", lambda mode, **kwargs: seen.update(kwargs))
    monkeypatch.setattr(main, "run_verify", lambda hypotheses, **kwargs: [])
    out = tmp_path / "out"
    assert main.mode_v2(main.build_parser().parse_args(
        ["--mode", "hybrid", "--input", str(source), "--output-dir", str(out), *extra])) == 0
    assert seen["auto_lessons"] is expected and seen["run_dir"] == out


@pytest.mark.parametrize("extra, expected", [((), True), (("--no-auto-lessons",), False)])
def test_scan_hands_the_flag_and_its_folder_to_the_healer(tmp_path, monkeypatch, extra, expected):
    from test_scan_pipeline import _Analyzer, _repo, _run_main

    seen = {}
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: _Analyzer())
    monkeypatch.setattr(main, "LLMClient", lambda **kwargs: SimpleNamespace(model=kwargs["model"]))
    monkeypatch.setattr(main, "build_healer", lambda mode, **kwargs: seen.update(kwargs))
    monkeypatch.setattr(main, "execute_scan", lambda plan, **kwargs: {"detection": {"failed": 0}})
    out = tmp_path / "out"
    assert _run_main(monkeypatch, ["--mode", "scan", "--input", str(_repo(tmp_path)), "--output-dir", str(out),
                                   "--backend", "openai", "--yes", *extra]) == 0
    assert seen["auto_lessons"] is expected and seen["run_dir"] == out


def test_a_fixed_notebook_is_read_once(monkeypatch):
    _heals(monkeypatch)
    fixed = _healer(auto_lessons=False)
    _healer().learn(_h(), [{"round": 0, "verdict_before": UNSUPPORTED, "reason_before": "ERROR: x",
                            "verdict_after": CONFIRMED, "patch": {"definitions": STUB}}], {"verdict": CONFIRMED})
    result = verify_with_healing(_h("b"), healer=fixed, source=SOURCE, llm="spec").to_dict()
    assert result["notebook_version"] == fixed.lessons_version != lessons.notebook_version()
    assert "Automatic repair" not in fixed.llm.tasks[0]
