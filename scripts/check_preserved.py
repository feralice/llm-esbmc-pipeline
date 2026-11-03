"""Whether a harness keeps the target function's body (and, for a nested target, the enclosing function's) as in
the original: the check the /self-healing command runs after each rewrite.

    python scripts/check_preserved.py original.py harness.py Class.method ["suspect expression"]
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verify.astutil import locate
from research_pipeline.verify.validation import target_preserved


def main(argv: list[str]) -> int:
    """Exit 0 preserved, 1 changed, 2 when the check cannot run (missing file, invalid Python, target not found)."""
    if len(argv) not in (3, 4):
        print(__doc__, file=sys.stderr)
        return 2
    original, harness, function, *expression = argv
    try:
        sources = [Path(original).read_text(encoding="utf-8"), Path(harness).read_text(encoding="utf-8")]
        trees = [ast.parse(source) for source in sources]
    except (OSError, SyntaxError) as exc:
        print(f"não deu para conferir: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 2
    for label, tree in zip(("original", "harness"), trees, strict=True):
        if locate(tree, function, *expression) is None:
            print(f"não deu para conferir: {function} não encontrada no {label}", file=sys.stderr)
            return 2
    preserved = target_preserved(*sources, function, *expression)
    print("preservado" if preserved else "alterado")
    return 0 if preserved else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
