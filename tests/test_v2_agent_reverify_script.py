import importlib.util
import json
from pathlib import Path

import pytest

from research_pipeline.verify import agent_arm, esbmc_run
from tests.test_verify_agent_arm import ORIGINAL, PRESERVED, _esbmc

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "v2_agent_reverify.py"


@pytest.fixture
def script():
    spec = importlib.util.spec_from_file_location("v2_agent_reverify", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _archived_run(tmp_path: Path) -> tuple[Path, Path, str]:
    """An agent-arm run whose hypothesis came from a slice; the full file sits in the sources folder."""
    sources = tmp_path / "sources"
    sources.mkdir()
    (sources / "orig.py").write_text(ORIGINAL, encoding="utf-8")
    hypothesis = {"file": str(tmp_path / "slice" / "orig.py"), "function": "ratio",
                  "suspect_expression": "total // count", "category": "division_by_zero"}
    hypothesis_id = agent_arm.BugHypothesis(**hypothesis).hypothesis_id
    case = tmp_path / "run" / "cases" / hypothesis_id
    case.mkdir(parents=True)
    (case / "harness.py").write_text(PRESERVED, encoding="utf-8")
    (case / "original.py").write_text(ORIGINAL, encoding="utf-8")
    (tmp_path / "run" / "agent_results.json").write_text(
        json.dumps([{"hypothesis": {**hypothesis, "hypothesis_id": hypothesis_id}, "verdict": "AGENT_FAILED"}]),
        encoding="utf-8")
    return tmp_path / "run", sources, hypothesis_id


def test_reverify_measures_like_the_agent_arm(script, tmp_path, monkeypatch):
    run, sources, hypothesis_id = _archived_run(tmp_path)
    monkeypatch.setattr(esbmc_run, "run_esbmc_direct", _esbmc())
    monkeypatch.setattr(agent_arm, "DIFFERENTIAL_RUNS", 3)
    pytest_dirs = []

    def fake_pytest(path, **kwargs):
        pytest_dirs.append(kwargs["out_dir"])
        return {"status": "not_generated", "path": "", "reason": "fake", "route": "direct"}

    monkeypatch.setattr(agent_arm, "esbmc_pytest", fake_pytest)
    seen = {}
    real = script.evaluate_harness

    def spy(*args, **kwargs):
        seen.update(kwargs)
        return real(*args, **kwargs)

    monkeypatch.setattr(script, "evaluate_harness", spy)
    out = tmp_path / "recheck.json"
    assert script.main([str(run), "--out", str(out), "--verification-sources", str(sources)]) == 0
    assert seen["original_path"] == sources / "orig.py"
    assert pytest_dirs == [tmp_path / "recheck" / hypothesis_id / "pytest"]
    assert not (run / "cases" / hypothesis_id / "pytest").exists()
    row = json.loads(out.read_text(encoding="utf-8"))[0]
    assert row["after"] == "CONFIRMED", row
    assert row["pytest"]["status"] == "not_generated"
    assert row["differential"]["level"] == "stubs"
