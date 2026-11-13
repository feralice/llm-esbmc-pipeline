import json
from pathlib import Path

import main
from research_pipeline.models import Finding


class _Recorder:
    def __init__(self):
        self.v2_variants = ("A1", "A2")
        self.seen = {}

    def analyze(self, unit):
        self.seen[unit.qualname] = tuple(self.v2_variants)
        return []


def test_auto_gives_each_function_only_its_variants(tmp_path, monkeypatch):
    source = tmp_path / "sample.py"
    source.write_text("def divide(a, b):\n    return a // b\n\ndef identity(x):\n    return x\n", encoding="utf-8")
    recorder = _Recorder()
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(main, "build_analyzer", lambda **kwargs: recorder)
    argv = ["--mode", "hybrid", "--v2-stage", "detection", "--input", str(source),
            "--output-dir", str(tmp_path / "out"), "--v2-variants", "auto"]
    assert main.mode_v2(main.build_parser().parse_args(argv)) == 0
    assert recorder.seen["divide"] == ("A2", "A16")
    assert recorder.seen["identity"] == ("A1", "A2")
    report = json.loads((tmp_path / "out" / "v2_verify_report.json").read_text())
    assert report["config"]["routing"] == "routing_v1"
