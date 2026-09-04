from __future__ import annotations

import json
from pathlib import Path

import main


def _write_eval(model_dir: Path, stem: str, findings: list[dict]) -> None:
    model_dir.mkdir(parents=True, exist_ok=True)
    payload = {"file": f"{stem}.py", "expected_bugs": [], "generated_bugs": findings}
    (model_dir / f"{stem}_eval.json").write_text(json.dumps(payload), encoding="utf-8")


def test_build_parser_accepts_ensemble_mode() -> None:
    parser = main.build_parser()
    args = parser.parse_args(["--mode", "ensemble", "--input", "a", "b", "--min-votes", "3"])
    assert args.mode == "ensemble"
    assert args.input == ["a", "b"]
    assert args.min_votes == 3


def test_mode_ensemble_writes_vote_report(tmp_path: Path) -> None:
    shared = {"function": "read_item", "category": "out_of_bounds", "expression": "items[i]", "line": 2}
    model_a = tmp_path / "model-a"
    model_b = tmp_path / "model-b"
    _write_eval(model_a, "sample", [shared])
    _write_eval(model_b, "sample", [shared])

    report_path = tmp_path / "votes.json"
    parser = main.build_parser()
    args = parser.parse_args(
        [
            "--mode", "ensemble",
            "--input", str(model_a), str(model_b),
            "--min-votes", "2",
            "--report", str(report_path),
        ]
    )

    exit_code = main.mode_ensemble(args)

    assert exit_code == 0
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["selected_count"] == 1
    assert report["candidates"][0]["models"] == ["model-a", "model-b"]


def test_mode_ensemble_requires_two_directories(tmp_path: Path, capsys) -> None:
    parser = main.build_parser()
    args = parser.parse_args(["--mode", "ensemble", "--input", str(tmp_path)])

    exit_code = main.mode_ensemble(args)

    assert exit_code == 1
    assert "2+ diretórios" in capsys.readouterr().err
