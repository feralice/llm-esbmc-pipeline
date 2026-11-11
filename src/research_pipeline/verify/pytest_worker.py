"""Run a generated pytest in a confined, disposable directory."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from confinement import IsolationUnavailable, confine_writes


def main() -> int:
    try:
        confine_writes(Path.cwd())
    except IsolationUnavailable as exc:
        print(f"worker isolation unavailable: {exc}", file=sys.stderr)
        return 125
    import pytest

    return pytest.main(["-q", "--tb=short", "-p", "no:cacheprovider", "--basetemp=.pytest-tmp", sys.argv[1]])


if __name__ == "__main__":
    raise SystemExit(main())
