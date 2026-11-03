import subprocess
import sys
from datetime import date

import pytest

from research_pipeline.verify.lessons import (
    add_repair,
    approved_repairs,
    notebook_version,
)

NOTEBOOK = """---
name: reparos-aprendidos
description: x
---

# Learned repairs

### Annotate attributes that start as None
- Error: `ERROR: Cannot resolve nested attribute: <name>`
- What to do: annotate it.
- Source case: abc (nm_real_12), round 4.
- Approval date: 2026-10-27.

## Format of an approved repair

### <short title>
- Error: the first line.
"""


def _notebook(tmp_path, text=NOTEBOOK):
    path = tmp_path / "SKILL.md"
    path.write_text(text, encoding="utf-8")
    return path


def test_approved_repairs_are_the_rules_before_the_format_section(tmp_path):
    rules = approved_repairs(_notebook(tmp_path))
    assert rules.startswith("### Annotate attributes") and "short title" not in rules
    assert approved_repairs(_notebook(tmp_path, NOTEBOOK.split("### Annotate")[0] + "## Format of an approved repair\n")) == ""


def test_add_repair_inserts_before_the_format_section_and_changes_the_version(tmp_path):
    path = _notebook(tmp_path)
    before = notebook_version(path)
    add_repair("Name a dict.get default", "ERROR: Unsupported call", "bind the default to a local.",
               "def456 (dz_real_02), round 2", path=path, today=date(2026, 11, 2))
    text = path.read_text(encoding="utf-8")
    assert text.index("### Name a dict.get default") < text.index("## Format of an approved repair")
    assert "- Approval date: 2026-11-02." in text and notebook_version(path) != before
    assert "### Name a dict.get default" in approved_repairs(path)


@pytest.mark.parametrize("title, error", [("Annotate attributes that start as None", "ERROR: x"),
                                          ("Two\nlines", "ERROR: x"), ("Fine", ""), ("Fine", "no prefix")])
def test_add_repair_refuses_a_bad_rule(tmp_path, title, error):
    path = _notebook(tmp_path)
    with pytest.raises(ValueError):
        add_repair(title, error, "do it", "case", path=path, today=date(2026, 11, 2))
    assert path.read_text(encoding="utf-8") == NOTEBOOK


def test_add_repair_refuses_a_notebook_without_the_format_section(tmp_path):
    path = _notebook(tmp_path, NOTEBOOK.split("## Format")[0])
    with pytest.raises(ValueError):
        add_repair("Fine", "ERROR: x", "do it", "case", path=path, today=date(2026, 11, 2))


def test_check_preserved_script_exit_codes(tmp_path):
    original = tmp_path / "o.py"
    original.write_text("def f(x):\n    return 10 // x\n", encoding="utf-8")
    same, changed = tmp_path / "h.py", tmp_path / "c.py"
    same.write_text(original.read_text() + "\nf(nondet_int())\n", encoding="utf-8")
    changed.write_text("def f(x):\n    return 10 // (x or 1)\n", encoding="utf-8")
    run = [sys.executable, "scripts/check_preserved.py", str(original)]
    ok = subprocess.run([*run, str(same), "f"], capture_output=True, text=True, check=False)
    bad = subprocess.run([*run, str(changed), "f"], capture_output=True, text=True, check=False)
    assert (ok.returncode, ok.stdout.strip()) == (0, "preservado")
    assert (bad.returncode, bad.stdout.strip()) == (1, "alterado")


def test_add_repair_script_writes_the_rule(tmp_path):
    path = _notebook(tmp_path)
    done = subprocess.run([sys.executable, "scripts/add_repair.py", "--notebook", str(path), "--title", "Fine",
                           "--error", "ERROR: x", "--what", "do it", "--case", "c1"],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0 and "### Fine" in path.read_text(encoding="utf-8")


class _AskedLLM:
    def __init__(self):
        self.tasks = []

    def complete(self, system, user, *, json_mode=False):
        from types import SimpleNamespace

        self.tasks.append(user)
        return SimpleNamespace(harness='{"edits": [], "definitions": ""}')


def _propose(lessons):
    from research_pipeline.verify.healing import Healer
    from research_pipeline.verify.hypothesis import BugHypothesis

    llm = _AskedLLM()
    healer = Healer(llm, None, lessons=lessons)
    healer.propose(BugHypothesis("x.py", "f", "10 // x", line=2), "def f(x):\n    return 10 // x\n",
                   "ESBMC_ERROR", "ERROR: Cannot resolve nested attribute: y", [])
    return healer, llm.tasks[0]


def test_batch_healing_sees_the_approved_repairs_and_records_their_version():
    healer, task = _propose("### Annotate attributes\n- What to do: annotate.")
    assert "Repairs the researcher approved for earlier cases" in task and "### Annotate attributes" in task
    assert "+notes:" in healer.config_label


def test_no_section_and_no_version_without_approved_repairs():
    healer, task = _propose("")
    assert "Repairs the researcher approved" not in task and "notes" not in healer.config_label


def test_healer_reads_the_notebook_by_default():
    from research_pipeline.verify.healing import Healer

    assert Healer(_AskedLLM(), None).lessons == approved_repairs()
