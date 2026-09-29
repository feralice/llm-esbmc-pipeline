"""Offline baseline for the rewrite stage: original-code probes only, no LLM.

Reads only the manifest's detection fields (file, function, category,
expression); harness files and ground truth are never opened.
"""

from __future__ import annotations

import json
import time
from collections import Counter
from hashlib import sha256
from pathlib import Path

from ..preprocess import preprocess_file
from .pipeline import (
    _REWRITE_CATEGORIES,
    ScanCandidate,
    _find_unit,
    _most_informative,
    _try_native,
    _try_real_body_driver,
)


def _candidates(manifest_path: Path) -> list[tuple[str, ScanCandidate]]:
    items = json.loads(manifest_path.read_text(encoding="utf-8"))["items"]
    return [
        (str(item["id"]), ScanCandidate(
            file=str(manifest_path.parent / item["detection_file"]),
            function=str(item["function"]),
            category=str(item["categories"][0]),
            expression=str(item.get("expression", "")),
        ))
        for item in items
    ]


def _probe(case_id: str, candidate: ScanCandidate, harness_dir: Path, bound: int, timeout: int) -> dict:
    started = time.monotonic()
    diagnostics = []
    unit = _find_unit(preprocess_file(Path(candidate.file)), candidate.function)
    result = None
    if unit is not None and getattr(unit, "kind", "function") != "module":
        result = _try_native(
            candidate, finding_id=f"{case_id}_native", esbmc_command=None, bound=bound,
            timeout_seconds=timeout, harness_dir=harness_dir, diagnostics=diagnostics,
        )
        if result is None:
            result = _try_real_body_driver(
                candidate, unit, finding_id=f"{case_id}_real", esbmc_command=None, bound=bound,
                timeout_seconds=timeout, harness_dir=harness_dir, use_ablation=False,
                diagnostics=diagnostics,
            )
    diagnostic = _most_informative(diagnostics)
    return {
        "id": case_id,
        "candidate": candidate.to_dict(),
        "tier": result.classification if result else "inconclusive",
        "harness_tier": result.harness_tier if result else "",
        "esbmc_status": result.esbmc_status if result else "",
        "esbmc_summary": result.esbmc_summary if result else "",
        "diagnostic": {
            "kind": "unit_not_found" if unit is None else diagnostic.kind,
            "message": diagnostic.message, "raw_log_path": diagnostic.raw_log_path,
        },
        "rewrite_eligible": (
            result is None and unit is not None
            and candidate.category in _REWRITE_CATEGORIES and bool(candidate.expression.strip())
        ),
        "seconds": round(time.monotonic() - started, 2),
    }


def evaluate_offline(manifest_path: str, output_dir: str, *, per_case_timeout: int, bound: int = 5) -> dict:
    manifest = Path(manifest_path)
    out = Path(output_dir)
    (out / "cases").mkdir(parents=True, exist_ok=True)
    harness_dir = out / "harnesses"
    harness_dir.mkdir(exist_ok=True)

    records = []
    for case_id, candidate in _candidates(manifest):
        record = _probe(case_id, candidate, harness_dir, bound, per_case_timeout)
        (out / "cases" / f"{case_id}.json").write_text(json.dumps(record, indent=2), encoding="utf-8")
        records.append(record)
        print(f"[{len(records)}] {case_id:16s} {record['tier']:18s} {record['diagnostic']['kind']}")

    summary = {
        "cases": len(records),
        "by_tier": dict(Counter(r["tier"] for r in records)),
        "by_diagnostic": dict(Counter(r["diagnostic"]["kind"] for r in records if r["tier"] == "inconclusive")),
        "rewrite_stage": {
            "status": "not_run_offline",
            "eligible_for_rewrite": sum(r["rewrite_eligible"] for r in records),
        },
        "config": {
            "manifest": str(manifest.resolve()), "per_case_timeout": per_case_timeout, "bound": bound,
            # function/expression/category are the manifest's gold localization, as in --v2-stage synthesis.
            "candidate_source": "oracle_localized",
        },
        "inputs": {
            r["id"]: sha256(Path(r["candidate"]["file"]).read_bytes()).hexdigest() for r in records
        },
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("output_dir")
    parser.add_argument("--timeout", type=int, default=30)
    cli = parser.parse_args()
    print(json.dumps(evaluate_offline(cli.manifest, cli.output_dir, per_case_timeout=cli.timeout), indent=2))
