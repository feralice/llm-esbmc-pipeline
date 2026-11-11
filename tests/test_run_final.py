"""Exercise the real shell with fake local executables and disposable outputs."""

import os
import shutil
import subprocess
from pathlib import Path

import pytest


def _run(tmp_path, failed_stage, *, resume=False):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    source = Path(__file__).resolve().parents[1] / "scripts/run_final.sh"
    shutil.copy(source, scripts / "run_final.sh")
    fake = tmp_path / "fake-python"
    fake.write_text("#!/bin/sh\n"
                    "case \"$1\" in\n"
                    "src/main.py) stage=1;;\n"
                    "scripts/v2_replay_specs.py) stage=2;;\n"
                    "scripts/v2_orchestrate.py) case \"$2\" in *control*) stage=3;; *) stage=4;; esac;;\n"
                    "scripts/v2_validate.py) stage=5;;\n"
                    "esac\n"
                    "echo \"$stage\" >> stages\n"
                    "[ \"$stage\" = \"$FAIL_STAGE\" ] && exit 42\n"
                    "exit 0\n")
    fake.chmod(0o755)
    if resume:
        output = tmp_path / "artifacts/v2/final-test"
        (output / "control").mkdir(parents=True)
        (output / "v2_verify_report.json").write_text("{}")
        (output / "control/report_0of1.json").write_text("{}")
    done = subprocess.run(["bash", str(scripts / "run_final.sh"), "test"], cwd=tmp_path,
                          env={**os.environ, "PY": str(fake), "FAIL_STAGE": str(failed_stage)},
                          capture_output=True, text=True, check=False)
    return done, (tmp_path / "stages").read_text().splitlines()


@pytest.mark.parametrize("failed_stage", [1, 2, 3, 4, 5])
def test_failed_stage_stops_the_run_and_returns_failure(tmp_path, failed_stage):
    done, stages = _run(tmp_path, failed_stage)
    assert done.returncode != 0
    assert stages == [str(i) for i in range(1, failed_stage + 1)]
    assert " done" not in done.stdout


@pytest.mark.parametrize("resume,expected", [(False, ["1", "2", "3", "4", "5"]),
                                           (True, ["3", "4", "5"])])
def test_successful_run_and_existing_output_resume(tmp_path, resume, expected):
    done, stages = _run(tmp_path, 0, resume=resume)
    assert done.returncode == 0
    assert stages == expected
    assert " done" in done.stdout
