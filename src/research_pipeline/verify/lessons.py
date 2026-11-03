"""The repair notebook (skills/reparos-aprendidos/SKILL.md): rules the researcher approved after a harness
ESBMC-Python refused was rewritten into one it checks. The agent arm, batch self-healing and the interactive
/self-healing command all read it; only ``add_repair``, run after her approval, writes it."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

NOTEBOOK = Path(__file__).with_name("skills") / "reparos-aprendidos" / "SKILL.md"
_FORMAT = "## Format of an approved repair"


def approved_repairs(path: Path = NOTEBOOK) -> str:
    """The ``###`` rules above the format section, as written."""
    text = Path(path).read_text(encoding="utf-8").split(_FORMAT)[0]
    start = text.find("\n### ")
    return text[start + 1:].strip() if start >= 0 else ""


def notebook_version(path: Path = NOTEBOOK) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def add_repair(title: str, error: str, what: str, case: str, *, path: Path = NOTEBOOK, today: date) -> None:
    fields = {"title": title, "error": error, "what": what, "case": case}
    problems = [f"{name} is empty" for name, value in fields.items() if not value.strip()]
    problems += [f"{name} spans more than one line" for name, value in fields.items() if "\n" in value.strip()]
    if error.strip() and "ERROR" not in error:
        problems.append("error must quote ESBMC's first ERROR: line")
    text = Path(path).read_text(encoding="utf-8")
    if _FORMAT not in text:
        problems.append(f"the notebook has no '{_FORMAT}' section")
    if f"### {title.strip()}\n" in text.split(_FORMAT)[0]:
        problems.append(f"a rule called {title.strip()!r} already exists")
    if problems:
        raise ValueError("; ".join(problems))
    rule = (f"### {title.strip()}\n- Error: `{error.strip().strip('`')}`\n- What to do: {what.strip()}\n"
            f"- Source case: {case.strip()}\n- Approval date: {today.isoformat()}.\n\n")
    head, tail = text.split(_FORMAT, 1)
    Path(path).write_text(head.rstrip("\n") + "\n\n" + rule + _FORMAT + tail, encoding="utf-8")
