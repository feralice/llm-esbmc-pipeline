from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from research_pipeline.verification import esbmc_runner


def test_direct_esbmc_reports_no_violation_only_within_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "sample.py"
    source.write_text("def f(x):\n    return x + 1\n", encoding="utf-8")
    monkeypatch.setattr(esbmc_runner.shutil, "which", lambda _name: "/usr/bin/esbmc")
    monkeypatch.setattr(
        esbmc_runner.subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout="Generated 1 VCC(s)\nVERIFICATION SUCCESSFUL\n",
            stderr="",
            returncode=0,
        ),
    )

    result = esbmc_runner.run_esbmc_direct(
        source, bound=4, timeout_seconds=9, output_dir=tmp_path / "artifacts",
    )

    assert result.status == "no_violation_found"
    assert result.details["outcome"] == "not_confirmed_within_bound"
    assert result.details["timeout_seconds"] == 9
    assert "até o bound analisado" in result.summary


@pytest.mark.parametrize("bound", [0, -1, True])
def test_invalid_bound_fails_before_esbmc(bound) -> None:
    with pytest.raises(ValueError, match="bound"):
        esbmc_runner.run_esbmc_direct("unused.py", bound=bound)
