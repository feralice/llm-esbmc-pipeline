"""What the installed ESBMC-Python accepts, read from its own checkout: the frontend README's sections and
the regression tests that pass. Rebuilt whenever the checkout's commit changes, so the self-healing prompt
follows ESBMC as it evolves instead of hand-written notes (verify/esbmc_python_notes.md, measured on 8.5)."""

from __future__ import annotations

import ast
import json
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

README = Path("src/python-frontend/README.md")
REGRESSION = Path("regression/python")
_PASSING = {"CORE", "THOROUGH"}
KNOWLEDGE_CACHE = Path.home() / ".cache" / "llm_esbmc" / "esbmc_knowledge"
_MAX_SECTIONS, _MAX_TESTS = 2, 3
_TEST_CHARS = 800
_STOP = {"the", "and", "for", "not", "with", "this", "that", "from", "are", "can", "line", "function",
         "error", "file", "type", "add", "its", "has", "was", "but", "only", "into", "use", "main"}


@dataclass(frozen=True)
class Snippet:
    source: str
    title: str
    text: str


@dataclass
class KnowledgeIndex:
    commit: str
    sections: list[Snippet] = field(default_factory=list)
    tests: list[Snippet] = field(default_factory=list)


def _commit(root: Path) -> str:
    try:
        done = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True,
                              timeout=30, check=False)
    except OSError:
        return ""
    return done.stdout.strip() if done.returncode == 0 else ""


def _sections(text: str) -> list[Snippet]:
    found, title, body = [], "", []
    for line in [*text.splitlines(), "## "]:
        heading = re.match(r"^#{2,3} (.*)$", line)
        if heading:
            if title and any(b.strip() for b in body):
                found.append(Snippet(str(README), title, "\n".join(body).strip()))
            title, body = heading.group(1).strip(), []
        else:
            body.append(line)
    return found


def _tests(root: Path) -> list[Snippet]:
    found = []
    for desc in sorted((root / REGRESSION).glob("*/test.desc")):
        lines = desc.read_text(encoding="utf-8", errors="replace").splitlines()
        main = desc.parent / "main.py"
        if lines and lines[0].strip() in _PASSING and main.exists():
            found.append(Snippet(str(REGRESSION / desc.parent.name), desc.parent.name,
                                 main.read_text(encoding="utf-8", errors="replace")[:_TEST_CHARS]))
    return found


def build_index(esbmc_root: Path) -> KnowledgeIndex:
    readme = esbmc_root / README
    sections = _sections(readme.read_text(encoding="utf-8", errors="replace")) if readme.exists() else []
    return KnowledgeIndex(_commit(esbmc_root), sections, _tests(esbmc_root))


def load_index(esbmc_root: Path, cache_dir: Path) -> KnowledgeIndex:
    commit = _commit(esbmc_root)
    cached = cache_dir / f"{commit}.json"
    if commit and cached.exists():
        data = json.loads(cached.read_text(encoding="utf-8"))
        return KnowledgeIndex(data["commit"], [Snippet(**s) for s in data["sections"]],
                              [Snippet(**s) for s in data["tests"]])
    index = build_index(esbmc_root)
    if index.commit:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(asdict(index)), encoding="utf-8")
    return index


def esbmc_root_of(esbmc_command: list[str]) -> Path | None:
    """The checkout an ESBMC binary was built from, found by walking up from it (or from its wrapper's target)."""
    if not esbmc_command:
        return None
    start = Path(esbmc_command[0]).expanduser()
    if start.is_file() and start.suffix == ".sh":
        target = re.search(r"(/\S+/esbmc)\b", start.read_text(encoding="utf-8", errors="replace"))
        start = Path(target.group(1)) if target else start
    for folder in [start, *start.parents]:
        if (folder / README).exists():
            return folder
    return None


def _words(text: str) -> set[str]:
    return {w.lower() for w in re.findall(r"[A-Za-z_][A-Za-z_]{2,}", text)} - _STOP


def _constructs(code: str) -> set[str]:
    """AST node kinds, operators and method names of the refused code; partial code still gives its words."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return set()
    found = {type(node).__name__.lower() for node in ast.walk(tree)}
    found |= {node.attr.lower() for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    if any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mod) and isinstance(n.left, ast.Constant)
           for n in ast.walk(tree)):
        found.add("%")
    return found - {"module", "expr", "load", "store", "name", "constant", "assign"}


def _score(snippet: Snippet, words: set[str], constructs: set[str]) -> int:
    text = f"{snippet.title} {snippet.text}"
    mine = _words(text)
    hits = len(words & mine) + 2 * len(constructs & (mine | _constructs(snippet.text)))
    return hits + (2 if "%" in constructs and "%" in text else 0)


def lookup(index: KnowledgeIndex, message: str, code: str, max_chars: int = 4000) -> str:
    """The README sections and passing tests closest to an ESBMC refusal, most relevant first."""
    words, constructs = _words(message) | _words(code), _constructs(code)
    parts = []
    for pool, limit, label in ((index.sections, _MAX_SECTIONS, "README"), (index.tests, _MAX_TESTS, None)):
        ranked = sorted(((_score(s, words, constructs), i, s) for i, s in enumerate(pool)), key=lambda t: (-t[0], t[1]))
        for score, _, snippet in ranked[:limit]:
            if score:
                heading = f"### README: {snippet.title}" if label else f"### {snippet.source} (ESBMC accepts this)"
                parts.append(f"{heading}\n{snippet.text}")
    return "\n\n".join(parts)[:max_chars]
