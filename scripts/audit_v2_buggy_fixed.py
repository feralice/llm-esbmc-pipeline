"""Run ESBMC on every V2 buggy harness and its fixed counterpart.

Usage:
  python scripts/audit_v2_buggy_fixed.py [--ids av_real_01 ...] [--jobs 8]

Buggy harness: dataset/v2_real_world/bugs/<id>.py
Fixed harness: dataset/v2_real_world/bugs/<id>_fixed.py (same property, patched code)
A fixed harness may start with `# esbmc: <flags>` (e.g. `--unwind 12` for a
loop the patch keeps); the same flags are then used for BOTH runs so the
pair stays comparable.
Writes dataset/v2_real_world/esbmc_audit.json.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset" / "v2_real_world"
OUTPUT = DATASET / "esbmc_audit.json"
BASE_FLAGS = ["--z3", "--unwind", "6"]
DEFAULT_TIMEOUT = "20s"

_VCC = re.compile(r"Generated (\d+) VCC\(s\), (\d+) remaining")
_PROPERTY_LINE = re.compile(r"^\s*(?:file \S+ )?line (\d+)", re.MULTILINE)
_DIRECTIVE = re.compile(r"^# esbmc: (.+)$", re.MULTILINE)
_UNCAUGHT = re.compile(r"uncaught exception: (\w+)")


def esbmc_property(violated_block: str, harness_name: str) -> str:
    """Name the violated property the way ESBMC prints it (the symptom).

    Harness asserts -> "assertion"; checks raised inside ESBMC's own
    operational models (string.c, libm) -> "model_check"; loop-bound
    artefacts -> "unwinding_assertion", which is never a bug.
    """
    if not violated_block:
        return ""
    if "unwinding assertion" in violated_block:
        return "unwinding_assertion"
    match = _UNCAUGHT.search(violated_block)
    if match:
        return match.group(1)
    if "Missing return statement" in violated_block:
        return "missing_return"
    if "dereference failure" in violated_block:
        return "null_dereference"
    if "arithmetic overflow" in violated_block:
        return "arithmetic_overflow"
    first_line = violated_block.strip().splitlines()[0]
    if first_line.startswith("file ") and harness_name not in first_line:
        return "model_check"
    return "assertion"


def classify(output: str) -> str:
    """Map ESBMC output to failed / successful / timeout / unknown / error."""
    if "Timed out" in output:
        return "timeout"
    verdicts = re.findall(r"VERIFICATION (FAILED|SUCCESSFUL|UNKNOWN)", output)
    if not verdicts:
        return "error"
    return verdicts[-1].lower()


def _flags_for(item: dict, fixed: Path) -> list[str]:
    flags = list(BASE_FLAGS)
    directive = _DIRECTIVE.search(fixed.read_text(encoding="utf-8")) if fixed.is_file() else None
    if directive:
        flags = ["--z3", *directive.group(1).split()]
    recommended = str(item.get("recommended_flags") or "")
    if recommended.startswith("--incremental-bmc"):
        flags = ["--z3", "--incremental-bmc"]
    if "--timeout" in flags:
        return flags
    timeout = str(item.get("recommended_timeout") or DEFAULT_TIMEOUT).split()[0]
    return [*flags, "--timeout", timeout]


def run_one(path: Path, flags: list[str], esbmc: str = "esbmc") -> dict:
    command = [esbmc, *flags, str(path)]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=180, check=False)
        output = proc.stdout + proc.stderr
    except subprocess.TimeoutExpired:
        output = "Timed out (wall clock)"
    vccs = _VCC.findall(output)
    violated = output.split("Violated property:", 1)
    block = violated[1].strip().split("\n\n", 1)[0] if len(violated) == 2 else ""
    property_text = " | ".join(line.strip() for line in block.splitlines()[:3])
    match = _PROPERTY_LINE.search(block)
    property_line = int(match.group(1)) if match else None
    return {
        "esbmc_property": esbmc_property(block, path.name),
        "command": " ".join(command[:-1] + [str(path.relative_to(ROOT))]),
        "verdict": classify(output),
        "vccs": [int(total) for total, _ in vccs],
        "violated_property": property_text,
        "violated_line": property_line,
        "conversion_error": "ERROR:" in output and "VERIFICATION" not in output,
        "tail": output.strip().splitlines()[-3:],
    }


def audit_item(item: dict, esbmc: str = "esbmc") -> dict:
    buggy = DATASET / "bugs" / item["harness_file"]
    fixed = DATASET / "bugs" / item["harness_file"].replace(".py", "_fixed.py")
    flags = _flags_for(item, fixed)
    return {
        "id": item["id"],
        "buggy": run_one(buggy, flags, esbmc),
        "fixed": run_one(fixed, flags, esbmc) if fixed.is_file() else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ids", nargs="*")
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--esbmc", default="esbmc", help="ESBMC binary (default: the one on PATH)")
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    items = json.loads((DATASET / "ground_truths.json").read_text(encoding="utf-8"))["items"]
    if args.ids:
        items = [item for item in items if item["id"] in set(args.ids)]
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda item: audit_item(item, args.esbmc), items))

    output = args.output
    previous = json.loads(output.read_text(encoding="utf-8")) if output.is_file() else {}
    merged = {**previous.get("results", {}), **{r["id"]: r for r in results}}
    payload = {"esbmc": args.esbmc, "esbmc_flags": BASE_FLAGS, "default_timeout": DEFAULT_TIMEOUT,
               "results": merged}
    output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for result in results:
        fixed = result["fixed"]["verdict"] if result["fixed"] else "-"
        print(f"{result['id']:12} buggy={result['buggy']['verdict']:10} fixed={fixed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
