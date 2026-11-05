import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "v2_consult", Path(__file__).resolve().parents[1] / "scripts/v2_consult.py")
v2_consult = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v2_consult)


def _result(hid: str, attempts: list[dict]) -> dict:
    return {"hypothesis": {"hypothesis_id": hid, "file": "bugs/a.py", "function": "f", "suspect_expression": "x[0]",
                           "line": 0, "trigger_condition": "x empty", "category": "", "oracle": ""},
            "verdict": "UNSUPPORTED", "reason": "the receiver cannot subclass it", "attempts": attempts}


def _root(tmp_path: Path) -> Path:
    (tmp_path / "bugs").mkdir()
    (tmp_path / "bugs" / "a.py").write_text("def f(x):\n    return x[0]\n", encoding="utf-8")
    (tmp_path / "programs").mkdir()
    (tmp_path / "programs" / "h_a0.py").write_text("# harness\n", encoding="utf-8")
    return tmp_path


def test_a_case_refused_before_the_harness_gets_the_original_and_the_refusal(tmp_path):
    root, seen = _root(tmp_path), []

    def agent(prompt, cwd, timeout):
        seen.append(prompt)
        (cwd / "opiniao.md").write_text("ok", encoding="utf-8")
        return "DONE"

    built = [{"attempt": 0, "replay_program_path": "programs/h_a0_replay.py", "message": "ERROR: x"}]
    results = [_result("refused", []), _result("built", built)]
    out = tmp_path / "C"
    assert v2_consult.consult(results, out, agent, sources=None, root=root, esbmc="esbmc", timeout_seconds=1) == [
        "refused", "built"]
    refused = out / "refused"
    assert (refused / "original.py").exists() and not (refused / "harness_pipeline.py").exists()
    assert "receiver cannot subclass" in (refused / "recusa.txt").read_text(encoding="utf-8")
    assert "recusa.txt" in seen[0] and "harness_pipeline.py: o harness" not in seen[0]
    assert (out / "built" / "harness_pipeline.py").read_text(encoding="utf-8") == "# harness\n"
    assert "ERROR: x" in (out / "built" / "erro_esbmc.txt").read_text(encoding="utf-8")
    assert "harness_pipeline.py: o harness" in seen[1]
    assert all(chr(0x2014) not in prompt for prompt in seen)
    assert v2_consult.consult(results, out, agent, sources=None, root=root, esbmc="esbmc", timeout_seconds=1) == []
