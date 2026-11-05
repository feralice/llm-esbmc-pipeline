"""The repair notebook (skills/reparos-aprendidos/SKILL.md): rules learned after a harness ESBMC-Python refused
was rewritten into one it checks. The agent arm, batch self-healing and the interactive /self-healing command all
read it. ``add_repair`` writes a rule the researcher approved; ``add_auto_lesson`` writes, during a run, a repair
that made ESBMC reach a verdict (Fernanda's decision of 05/11: new lessons always enter)."""

from __future__ import annotations

import difflib
import fcntl
import hashlib
import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import date
from itertools import pairwise
from pathlib import Path

from .agent_arm import STUB_INDUCED
from .rounds import read_rounds

NOTEBOOK = Path(__file__).with_name("skills") / "reparos-aprendidos" / "SKILL.md"
_FORMAT = "## Format of an approved repair"
AUTO_ORIGIN = "automatica"
MAX_FIX_LINES = 60


def _path(path: Path | None) -> Path:
    return Path(path) if path is not None else NOTEBOOK


def _split(text: str) -> tuple[str, str] | None:
    """The rules and the format section, split at the heading on a line of its own."""
    marker = f"\n{_FORMAT}\n"
    if marker not in text:
        return None
    head, tail = text.split(marker, 1)
    return head, tail


def _rules(text: str) -> str:
    parts = _split(text)
    head = parts[0] if parts else text
    start = head.find("\n### ")
    return head[start + 1:].strip() if start >= 0 else ""


def _version(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:12]


def read_notebook(path: Path | None = None) -> tuple[str, str]:
    """The rules and the version, from one read (another run may add a lesson in between two reads)."""
    data = _path(path).read_bytes()
    return _rules(data.decode("utf-8")), _version(data)


def approved_repairs(path: Path | None = None) -> str:
    """The ``###`` rules above the format section, as written."""
    return read_notebook(path)[0]


def notebook_version(path: Path | None = None) -> str:
    """The hash the agent arm records for this skill (agent_arm.skill_versions), so both arms name one version."""
    return read_notebook(path)[1]


@contextmanager
def _locked(path: Path) -> Iterator[None]:
    """One writer at a time across processes; the lock lives outside skills/, which the agent arm copies."""
    key = hashlib.sha256(str(path.resolve()).encode("utf-8")).hexdigest()[:12]
    with open(Path(tempfile.gettempdir()) / f"llm_esbmc_notebook_{key}.lock", "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def _replace(path: Path, text: str) -> None:
    """A reader sees the old notebook or the new one, never half of it."""
    fd, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.chmod(temp, path.stat().st_mode & 0o777)
        os.replace(temp, path)
    except BaseException:
        Path(temp).unlink(missing_ok=True)
        raise


def _insert(path: Path, rule: str, head: str, tail: str) -> None:
    _replace(path, f"{head.rstrip()}\n\n{rule}{_FORMAT}\n{tail}")


def add_repair(title: str, error: str, what: str, case: str, *, path: Path | None = None, today: date) -> None:
    path = _path(path)
    fields = {"title": title, "error": error, "what": what, "case": case}
    problems = [f"{name} is empty" for name, value in fields.items() if not value.strip()]
    # One line per field: any line break (\r and unicode separators included) could forge a heading.
    problems += [f"{name} spans more than one line" for name, value in fields.items()
                 if len(value.strip().splitlines()) > 1]
    problems += [f"{name} quotes the format heading" for name, value in fields.items() if _FORMAT in value]
    if error.strip() and not error.strip().strip("`").startswith("ERROR"):
        problems.append("error must quote ESBMC's first ERROR: line")
    with _locked(path):
        parts = _split(path.read_text(encoding="utf-8"))
        if parts is None:
            problems.append(f"the notebook has no '{_FORMAT}' section")
        elif f"\n### {title.strip()}\n" in parts[0] + "\n":
            problems.append(f"a rule called {title.strip()!r} already exists")
        if problems:
            raise ValueError("; ".join(problems))
        rule = (f"### {title.strip()}\n- Error: `{error.strip().strip('`')}`\n- What to do: {what.strip()}\n"
                f"- Source case: {case.strip()}\n- Approval date: {today.isoformat()}.\n\n")
        _insert(path, rule, *parts)


def obstacle(message: str) -> str:
    """ESBMC's message without numbers and paths: the same obstacle on another line is still the same obstacle."""
    return re.sub(r"\S*/\S*|\d+", "", message)[:200]


def first_error(output: str) -> str:
    lines = output.splitlines()
    return next((line for line in lines if line.startswith("ERROR:")), lines[0] if lines else "")


def _one_line(text: str) -> str:
    return " ".join(str(text).split())


def lesson_key(error: str, fix: str) -> str:
    """The same obstacle fixed by the same added and removed lines, whatever the context lines around them."""
    changed = [line[1:].strip() for line in fix.splitlines()
               if line[:1] in "+-" and not line.startswith(("+++", "---")) and line[1:].strip()]
    return _version("\n".join([obstacle(_one_line(error)), *changed]).encode("utf-8"))


def add_auto_lesson(*, error: str, fix: str, reached: str, case: str, run: str, today: date,
                    path: Path | None = None) -> bool:
    """Append a repair as an approved lesson; False when the same lesson is already there. ``fix`` is a diff."""
    path = _path(path)
    error = _one_line(error).strip("`") or "(no message)"
    key = lesson_key(error, fix)
    # Every fix line keeps a diff prefix, so none can close the fence or open a heading.
    lines = [line if line[:1] in "+- @" else f" {line}" for line in fix.splitlines()]
    if len(lines) > MAX_FIX_LINES:
        lines = [*lines[:MAX_FIX_LINES], f" ... ({len(lines) - MAX_FIX_LINES} more lines)"]
    body = "\n".join(lines)
    rule = (f"### Automatic repair {key}: {error[:80]}\n- Origin: {AUTO_ORIGIN}\n- Error: `{error}`\n"
            f"- What to do: the change below made ESBMC reach {_one_line(reached)} without changing the target "
            f"function's behaviour.\n```diff\n{body}\n```\n- Source case: {_one_line(case)}\n"
            f"- Run: {_one_line(run) or 'unknown'}\n- Date: {today.isoformat()}.\n- Key: {key}\n\n")
    with _locked(path):
        parts = _split(path.read_text(encoding="utf-8"))
        if parts is None:
            raise ValueError(f"the notebook has no '{_FORMAT}' section")
        if f"\n- Key: {key}\n" in parts[0] + "\n":
            return False
        _insert(path, rule, *parts)
    return True


def teaches_repair(entry: dict | None) -> bool:
    """A case whose confirmation came from its own stub, or whose harness changed the target, teaches no repair."""
    return (entry is not None
            and STUB_INDUCED not in (entry.get("verdict"), (entry.get("first_attempt") or {}).get("verdict"))
            and (entry.get("differential") or {}).get("preservation") != "alterada"
            and entry.get("target_preserved") is not False)


def round_repairs(case_dir: Path, entry: dict | None) -> list[dict]:
    """The agent's rounds where ESBMC refused a harness and the next one reached a verdict."""
    if not teaches_repair(entry):
        return []
    case_dir = Path(case_dir)
    rounds = read_rounds(case_dir)
    return [{"caso": case_dir.name, "rodada": first.index, "erro": first_error(first.output),
             "diff": "".join(difflib.unified_diff(first.source.splitlines(keepends=True),
                                                  second.source.splitlines(keepends=True),
                                                  f"rodada {first.index:03d}", f"rodada {second.index:03d}"))}
            for first, second in pairwise(rounds)
            if first.kind == "refused" and second.kind == "verdict"]
