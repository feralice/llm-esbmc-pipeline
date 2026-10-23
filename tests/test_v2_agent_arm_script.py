import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "v2_agent_arm.py"


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("v2_agent_arm", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def esbmc_checkout(tmp_path):
    root = tmp_path / "esbmc-src"
    (root / "src" / "python-frontend").mkdir(parents=True)
    (root / "src" / "python-frontend" / "README.md").write_text("docs", encoding="utf-8")
    binary = root / "build" / "esbmc"
    binary.parent.mkdir()
    binary.write_text("#!/bin/sh\necho 'ESBMC version 9.9.9 64-bit'\n", encoding="utf-8")
    binary.chmod(0o755)
    for command in (["init", "-q"], ["add", "."], ["-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "x"]):
        subprocess.run(["git", "-C", str(root), *command], check=True)
    return binary


def _hypothesis(name: str) -> dict:
    return {"file": f"{name}.py", "function": "f", "suspect_expression": "a // b", "line": 0,
            "trigger_condition": name, "category": "", "oracle": ""}


def _report(path: Path, names: list[str]) -> Path:
    path.write_text(json.dumps({"results": [{"hypothesis": _hypothesis(n), "verdict": "AGENT_NEEDED", "reason": ""}
                                            for n in names]}), encoding="utf-8")
    return path


@pytest.fixture
def calls(script, monkeypatch):
    seen = []

    def fake_run(h, **kwargs):
        seen.append((h, kwargs))
        return {"hypothesis": h.to_dict(), "verdict": "NOT_CONFIRMED", "reason": "", "target_preserved": True}

    monkeypatch.setattr(script, "run_agent_arm", fake_run)
    monkeypatch.setattr(script, "make_agent", lambda *a, **k: (lambda *x: "DONE", False))
    monkeypatch.setattr(script, "verification_source", lambda h, sources: Path(h.file))
    return seen


def _run(script, tmp_path, esbmc, *extra, report=None):
    out = tmp_path / "out"
    argv = ["--esbmc", str(esbmc), "--out", str(out), "--verdicts", "AGENT_NEEDED", *extra]
    if report:
        argv = ["--report", str(report), *argv]
    assert script.main(argv) == 0
    return json.loads((out / "agent_results.json").read_text(encoding="utf-8"))


def test_variant_records_esbmc_commit_and_skill_versions(script, tmp_path, esbmc_checkout, calls):
    report = _report(tmp_path / "report.json", ["a"])
    results = _run(script, tmp_path, esbmc_checkout, "--project-skills", report=report)
    variant = results[0]["variant"]
    assert len(variant["esbmc_commit"]) == 40
    assert variant["esbmc_version"] == "ESBMC version 9.9.9 64-bit"
    assert set(variant["skills"]) == {"regras-harness", "reparos-aprendidos"}


def test_flags_reach_the_arm_and_default_stays_on(script, tmp_path, esbmc_checkout, calls):
    report = _report(tmp_path / "report.json", ["a"])
    _run(script, tmp_path, esbmc_checkout, "--project-skills", "--log-rounds", "--no-pytest", report=report)
    kwargs = calls[0][1]
    assert kwargs["project_skills"] and kwargs["log_rounds"]
    assert kwargs["differential"] is True and kwargs["pytest"] is False


def test_resume_skips_finished_cases(script, tmp_path, esbmc_checkout, calls):
    report = _report(tmp_path / "report.json", ["a", "b"])
    _run(script, tmp_path, esbmc_checkout, "--limit", "1", report=report)
    assert [h.trigger_condition for h, _ in calls] == ["a"]
    calls.clear()
    results = _run(script, tmp_path, esbmc_checkout, report=report)
    assert [h.trigger_condition for h, _ in calls] == ["b"]
    assert [r["hypothesis"]["trigger_condition"] for r in results] == ["a", "b"]


def test_sample_flag_runs_only_sampled_hypotheses(script, tmp_path, esbmc_checkout, calls):
    report = _report(tmp_path / "report.json", ["a", "b", "c"])
    sample = tmp_path / "sample.json"
    sample.write_text(json.dumps({"seed": 1, "size": 1, "source_run": "r", "hypotheses": [_hypothesis("b")]}),
                      encoding="utf-8")
    _run(script, tmp_path, esbmc_checkout, "--sample", str(sample), report=report)
    assert [h.trigger_condition for h, _ in calls] == ["b"]
