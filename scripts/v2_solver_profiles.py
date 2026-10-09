"""Experiment A (2026-10-09): does an ESBMC solver profile finish programs that convert but time out?

Runs every program of a verify report whose verdict is ESBMC_TIMEOUT or ESBMC_ERROR under the default
profile and under SMT-during-symex (``--z3 --smt-during-symex --smt-symex-guard``), same bound and
time limit, unwinding assertions kept. Reports time, verdict and the failed claims that are Python
exceptions or user assertions; a confirmation still needs the CPython replay, which this does not run.

  python scripts/v2_solver_profiles.py artifacts/v2/full-2026-10-05-regrounded/v2_verify_report.json \
      --out artifacts/v2/solver-profiles-2026-10-09
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

PROFILES = {"default": [], "smt_symex": ["--z3", "--smt-during-symex", "--smt-symex-guard"]}
_FAILED = re.compile(r"^\s+FAILED\s+\[([^\]]+)\]\s+line\s+(\d+)\s+(.*)$", re.M)


def run(esbmc: str, program: str, flags: list[str], timeout: int) -> dict:
    start = time.monotonic()
    try:
        done = subprocess.run([esbmc, program, "--unwind", "5", "--multi-property", *flags],
                              capture_output=True, text=True, timeout=timeout, check=False)
        output = done.stdout + done.stderr
    except subprocess.TimeoutExpired:
        return {"verdict": "TIMEOUT", "seconds": timeout, "failed": []}
    verdicts = re.findall(r"^VERIFICATION (\w+)", output, re.M)
    error = next((ln for ln in output.splitlines() if ln.startswith("ERROR")), "")
    failed = [f"{claim} line {line}: {msg}" for claim, line, msg in _FAILED.findall(output)
              if "exception" in msg or claim.split(".")[0] not in {"global"} and "assertion" in claim
              and "unwinding" not in msg and not claim.startswith("__")]
    return {"verdict": verdicts[-1] if verdicts else (error[:120] or "NO_VERDICT"),
            "seconds": round(time.monotonic() - start, 1), "failed": failed[:6]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report")
    parser.add_argument("--esbmc", default="/usr/local/bin/esbmc")
    parser.add_argument("--timeout", type=int, default=300)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    unique = {r["hypothesis"]["hypothesis_id"]: r for r in results
              if r["verdict"] in {"ESBMC_TIMEOUT", "ESBMC_ERROR"} and r.get("program_path")}
    jobs = [(hid, r, name, flags) for hid, r in unique.items() for name, flags in PROFILES.items()]

    def one(job):
        hid, r, name, flags = job
        return hid, name, run(args.esbmc, r["program_path"], flags, args.timeout)

    rows: dict[str, dict] = {}
    with ThreadPoolExecutor(args.workers) as pool:
        for hid, name, outcome in pool.map(one, jobs):
            r = unique[hid]
            row = rows.setdefault(hid, {"bug": Path(r["hypothesis"]["file"]).stem, "engine_verdict": r["verdict"],
                                        "program": r["program_path"]})
            row[name] = outcome
            print(f"{row['bug']:16} {name:10} {outcome['verdict']:12} {outcome['seconds']:6}s {outcome['failed'][:2]}",
                  flush=True)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "profiles.json").write_text(json.dumps(list(rows.values()), indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
