"""The repair notebook (skills/reparos-aprendidos/SKILL.md): rules the researcher approved after a harness
ESBMC-Python refused was rewritten into one it checks. The agent arm, batch self-healing and the interactive
/self-healing command all read it; only ``add_repair``, run after her approval, writes it."""

from __future__ import annotations

import hashlib
from datetime import date
from pathlib import Path

NOTEBOOK = Path(__file__).with_name("skills") / "reparos-aprendidos" / "SKILL.md"
_FORMAT = "## Format of an approved repair"


def _split(text: str) -> tuple[str, str] | None:
    """The rules and the format section, split at the heading on a line of its own."""
    marker = f"\n{_FORMAT}\n"
    if marker not in text:
        return None
    head, tail = text.split(marker, 1)
    return head, tail


def approved_repairs(path: Path = NOTEBOOK) -> str:
    """The ``###`` rules above the format section, as written."""
    text = Path(path).read_text(encoding="utf-8")
    parts = _split(text)
    head = parts[0] if parts else text
    start = head.find("\n### ")
    return head[start + 1:].strip() if start >= 0 else ""


def notebook_version(path: Path = NOTEBOOK) -> str:
    """The hash the agent arm records for this skill (agent_arm.skill_versions), so both arms name one version."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]


def add_repair(title: str, error: str, what: str, case: str, *, path: Path = NOTEBOOK, today: date) -> None:
    fields = {"title": title, "error": error, "what": what, "case": case}
    problems = [f"{name} is empty" for name, value in fields.items() if not value.strip()]
    # One line per field: any line break (\r and unicode separators included) could forge a heading.
    problems += [f"{name} spans more than one line" for name, value in fields.items()
                 if len(value.strip().splitlines()) > 1]
    problems += [f"{name} quotes the format heading" for name, value in fields.items() if _FORMAT in value]
    if error.strip() and not error.strip().strip("`").startswith("ERROR"):
        problems.append("error must quote ESBMC's first ERROR: line")
    text = Path(path).read_text(encoding="utf-8")
    parts = _split(text)
    if parts is None:
        problems.append(f"the notebook has no '{_FORMAT}' section")
    elif f"\n### {title.strip()}\n" in parts[0] + "\n":
        problems.append(f"a rule called {title.strip()!r} already exists")
    if problems:
        raise ValueError("; ".join(problems))
    rule = (f"### {title.strip()}\n- Error: `{error.strip().strip('`')}`\n- What to do: {what.strip()}\n"
            f"- Source case: {case.strip()}\n- Approval date: {today.isoformat()}.\n\n")
    head, tail = parts
    Path(path).write_text(f"{head.rstrip()}\n\n{rule}{_FORMAT}\n{tail}", encoding="utf-8")
