"""Bounded, attributed repository documentation for the harness agent."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

_EXTENSIONS = frozenset({".md", ".rst", ".txt"})
_MAX_FILE_BYTES = 128_000
_MAX_FILES = 2000
_MAX_EXCERPTS = 4
_MAX_EXCERPT_CHARS = 1200


@dataclass(frozen=True)
class DocumentationSnapshot:
    files: dict[str, str]
    digest: str


def documentation_snapshot(root: Path) -> DocumentationSnapshot:
    root = Path(root).resolve()
    candidates = [p for p in root.iterdir() if p.is_file() and p.name.lower().startswith("readme")]
    for name in ("doc", "docs"):
        folder = root / name
        if folder.is_dir() and not folder.is_symlink():
            candidates.extend(p for p in folder.rglob("*") if p.suffix.lower() in _EXTENSIONS)
    files: dict[str, str] = {}
    for path in sorted(candidates)[:_MAX_FILES]:
        try:
            if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_FILE_BYTES:
                continue
            if not path.resolve().is_relative_to(root):
                continue
            files[path.relative_to(root).as_posix()] = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
    digest = hashlib.sha256()
    for name, text in files.items():
        digest.update(name.encode("utf-8") + b"\0" + text.encode("utf-8") + b"\0")
    return DocumentationSnapshot(files, digest.hexdigest())


def relevant_documentation(snapshot: DocumentationSnapshot, root: Path, source: Path, function: str) -> str:
    try:
        module = ".".join(Path(source).resolve().relative_to(Path(root).resolve()).with_suffix("").parts)
    except ValueError:
        module = ""
    names = tuple(dict.fromkeys(n for n in (function, function.rsplit(".", 1)[-1], module) if n))
    matches = []
    for path, content in snapshot.files.items():
        lines = content.splitlines()
        for index, line in enumerate(lines):
            rank = next((i for i, name in enumerate(names)
                         if re.search(r"(?<![\w])" + re.escape(name) + r"(?![\w])", line)), None)
            if rank is not None:
                start, end = max(0, index - 2), min(len(lines), index + 4)
                excerpt = "\n".join(lines[start:end])[:_MAX_EXCERPT_CHARS]
                matches.append((rank, path, index + 1, excerpt))
    return "\n\n".join(f"{path}:{line}\n{excerpt}" for _, path, line, excerpt
                       in sorted(matches)[:_MAX_EXCERPTS])
