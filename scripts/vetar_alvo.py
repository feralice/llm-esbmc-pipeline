"""Check a GitHub repository before a scan or an issue: archived, deprecated in the README, stale.

    python scripts/vetar_alvo.py aws-samples/hardeneks boto/boto3 ...

Exit code 1 if any repository has an objection. Read-only: uses the GitHub API through ``gh``.
"""

from __future__ import annotations

import argparse
import base64
import json
import re
import subprocess
from datetime import date, datetime

STALE_DAYS = 365
_DEPRECATED = re.compile(r"(this (project|repository|repo|library|package|sample)\s+(is|has been)\s+(now\s+)?"
                         r"(deprecated|obsolete|archived|unmaintained|no longer maintained))"
                         r"|(\*\*deprecated\*\*)|(^>?\s*#*\s*deprecated\b)", re.IGNORECASE | re.MULTILINE)


def objections(info: dict, readme: str, *, today: date) -> list[str]:
    found = []
    if info.get("archived"):
        found.append("arquivado (somente leitura, não aceita issue)")
    if _DEPRECATED.search(readme or ""):
        found.append("README diz que o projeto está deprecated/sem manutenção")
    pushed = datetime.fromisoformat(info["pushed_at"].replace("Z", "+00:00")).date()
    if (today - pushed).days > STALE_DAYS:
        found.append(f"último push em {pushed} (mais de {STALE_DAYS} dias)")
    return found


def _gh(path: str) -> dict:
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True, check=False)
    return json.loads(out.stdout) if out.returncode == 0 and out.stdout else {}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("repos", nargs="+", metavar="DONO/REPO")
    bad = False
    for repo in parser.parse_args().repos:
        info = _gh(f"repos/{repo}")
        if not info:
            print(f"{repo}: não consegui consultar")
            bad = True
            continue
        readme_info = _gh(f"repos/{repo}/readme")
        readme = base64.b64decode(readme_info.get("content", "")).decode("utf-8", "replace") if readme_info else ""
        found = objections(info, readme, today=date.today())
        print(f"{repo}: {'OK' if not found else '; '.join(found)}")
        bad = bad or bool(found)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
