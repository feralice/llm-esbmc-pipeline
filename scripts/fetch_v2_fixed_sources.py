"""Fetch the fixed version of every V2 case that has a complete buggy source.

Used to measure false confirmations: running the pipeline on code where the bug was fixed must
never yield CONFIRMED. A fixed file is kept only when the target function exists and differs
(by AST, docstrings ignored) from the buggy complete source. Writes dataset/v2_real_world/fixed_full/.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from fetch_v2_full_sources import _download, _function, _raw_url, _same_function  # noqa: E402


def main() -> int:
    root = ROOT / "dataset" / "v2_real_world"
    manifest = json.loads((root / "manifest_full.json").read_text(encoding="utf-8"))
    out = root / "fixed_full"
    out.mkdir(exist_ok=True)
    report = {}
    for item in manifest["items"]:
        case_id, prov = str(item["id"]), item.get("provenance", {})
        if not item["detection_file"].startswith("detection_full"):
            report[case_id] = "no_complete_buggy_source"
            continue
        fixed_commit = prov.get("fixed_commit") or prov.get("commit_hash")
        if not fixed_commit:
            report[case_id] = "no_fixed_commit"
            continue
        buggy = _function((root / item["detection_file"]).read_text(encoding="utf-8"), str(item["function"]))
        source = _download(_raw_url(prov["repo_url"], fixed_commit, prov["source_file"]))
        time.sleep(0.2)
        fixed = _function(source, str(item["function"])) if source else None
        if source is None:
            status = "fetch_failed"
        elif fixed is None:
            status = "function_missing_in_fixed"
        elif _same_function(fixed, buggy):
            status = "function_unchanged_by_fix"
        else:
            (out / f"{case_id}.py").write_text(source, encoding="utf-8")
            status = f"fixed@{fixed_commit[:10]}"
        report[case_id] = status
        print(f"{case_id:14s} {status}")
    (out / "fetch_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"fixed {sum(v.startswith('fixed@') for v in report.values())}/{len(report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
