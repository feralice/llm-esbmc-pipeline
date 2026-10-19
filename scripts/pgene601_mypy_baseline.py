"""mypy baseline for the PGENE601 corpus: does mypy flag the bug or crash line, and does the fixed version keep the message."""

import json
import re
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1]); out = Path(sys.argv[2])
items = json.loads((root / "ground_truths.json").read_text())["items"]

def bug_lines(src: str, item) -> set[int]:
    lines = {item["line"]}
    rows = src.splitlines()
    for expr in item.get("crash_expressions") or []:
        key = expr.strip().splitlines()[0][:60]
        lines |= {i + 1 for i, r in enumerate(rows) if key in r}
    return lines

def mypy(path: Path, strict: bool) -> dict[int, list[str]]:
    cmd = [sys.executable, "-m", "mypy", "--ignore-missing-imports", "--follow-imports=skip",
           "--no-error-summary", "--show-error-codes", "--cache-dir=/dev/null", str(path)]
    if strict:
        cmd.insert(3, "--check-untyped-defs")
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=300, check=False)
    errs: dict[int, list[str]] = {}
    for ln in res.stdout.splitlines():
        m = re.match(r".*?:(\d+): error: (.*)", ln)
        if m:
            errs.setdefault(int(m.group(1)), []).append(m.group(2))
    return errs

rows = []
for it in items:
    buggy = root / "arquivo_com_bug" / it["file"]; fixed = root / "arquivo_corrigido" / it["file"]
    targets = bug_lines(buggy.read_text(), it)
    row = {"id": it["id"], "exc": it["expected_type"], "lines": sorted(targets)}
    for mode in (False, True):
        e = mypy(buggy, mode)
        hit = {l: e[l] for l in targets if l in e}
        key = "strict" if mode else "default"
        row[key] = hit
        row[key + "_total"] = sum(len(v) for v in e.values())
        if mode and hit:
            ef = mypy(fixed, True)
            msgs = {m for v in hit.values() for m in v}
            row["fixed_same_msg"] = any(m in msgs for v in ef.values() for m in v)
    rows.append(row)
    print(it["id"], "default" if row["default"] else "-", "strict" if row["strict"] else "-", flush=True)
out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
