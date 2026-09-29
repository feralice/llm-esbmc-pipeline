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

from ..models import CONFIDENCE_SOURCE_PIPELINE_PLACEHOLDER, Finding
from ..preprocess import preprocess_file
from .pipeline import (
    ScanCandidate,
    _find_unit,
    _most_informative,
    _try_native,
    _try_real_body_driver,
    _try_rewrite,
)
from .witness import ORACLE_CATEGORIES


def _candidates(manifest_path: Path) -> list[tuple[str, ScanCandidate]]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    excluded = {str(i) for i in payload.get("evaluation_policy", {}).get("patch_context_items", [])}
    items = [item for item in payload["items"] if str(item["id"]) not in excluded]
    return [
        (str(item["id"]), ScanCandidate(
            file=str(manifest_path.parent / item["detection_file"]),
            function=str(item["function"]),
            category=str(item["categories"][0]),
            expression=str(item.get("expression", "")),
        ))
        for item in items
    ]


def _probe(case_id: str, candidate: ScanCandidate, harness_dir: Path, bound: int, timeout: int,
           synthesizer=None, executor=None) -> dict:
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
    eligible = (
        result is None and unit is not None
        and candidate.category not in ORACLE_CATEGORIES and bool(candidate.expression.strip())
    )
    rewrite = None
    if synthesizer is not None and eligible:
        finding = Finding(
            id=case_id, stage="scan_candidate", finding_type="suspected_bug", category=candidate.category,
            title="", explanation="", evidence=[], verifiable=True, confidence="medium",
            confidence_source=CONFIDENCE_SOURCE_PIPELINE_PLACEHOLDER,
            metadata={"expression": candidate.expression},
        )
        stage = _try_rewrite(
            candidate, unit, finding, diagnostics, finding_id=case_id, synthesizer=synthesizer,
            executor=executor, esbmc_command=None, bound=bound, timeout_seconds=timeout,
            rewrite_dir=harness_dir.parent / "rewrites", rounds=4,
        )
        rewrite = {
            "status": stage.status, "reason": stage.reason, "esbmc_status": stage.esbmc_status,
            "esbmc_accepted": stage.esbmc_status in {"violation_found", "no_violation_found"},
            "tokens": stage.tokens, "rounds": stage.evidence.get("rounds", 0),
            "witness": stage.evidence.get("witness"), "esbmc_rejections": stage.evidence.get("esbmc_rejections", []),
        }
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
        "rewrite_eligible": eligible,
        "rewrite": rewrite,
        "seconds": round(time.monotonic() - started, 2),
    }


def evaluate_offline(
    manifest_path: str, output_dir: str, *, per_case_timeout: int, bound: int = 5,
    synthesizer=None, executor=None, max_total_tokens: int | None = None,
    shard: int = 0, shards: int = 1,
) -> dict:
    """Probe every case; with ``synthesizer``, also run the rewrite stage on eligible ones.

    Case files already on disk are reused, so an interrupted paid run resumes.
    """
    manifest = Path(manifest_path)
    out = Path(output_dir)
    (out / "cases").mkdir(parents=True, exist_ok=True)
    harness_dir = out / "harnesses"
    harness_dir.mkdir(exist_ok=True)

    records = []
    spent = 0
    for index, (case_id, candidate) in enumerate(_candidates(manifest)):
        if index % shards != shard:
            continue
        budget_left = max_total_tokens is None or spent < max_total_tokens
        case_file = out / "cases" / f"{case_id}.json"
        record = json.loads(case_file.read_text(encoding="utf-8")) if case_file.exists() else None
        if record is None or (synthesizer is not None and budget_left
                              and record["rewrite_eligible"] and not record.get("rewrite")):
            record = _probe(case_id, candidate, harness_dir, bound, per_case_timeout,
                            synthesizer if budget_left else None, executor)
            case_file.write_text(json.dumps(record, indent=2), encoding="utf-8")
        records.append(record)
        spent += int((record.get("rewrite") or {}).get("tokens") or 0)
        rewrite = (record.get("rewrite") or {}).get("status", "")
        print(f"[{len(records)}] {case_id:16s} {record['tier']:18s} {record['diagnostic']['kind']:14s} {rewrite}")

    rewrites = [r["rewrite"] for r in records if r.get("rewrite")]

    summary = {
        "cases": len(records),
        "by_tier": dict(Counter(r["tier"] for r in records)),
        "by_diagnostic": dict(Counter(r["diagnostic"]["kind"] for r in records if r["tier"] == "inconclusive")),
        "rewrite_stage": {
            "status": "ran" if rewrites else "not_run_offline",
            "eligible_for_rewrite": sum(r["rewrite_eligible"] for r in records),
            **({
                "by_status": dict(Counter(r["status"] for r in rewrites)),
                "esbmc_accepted_rewrite": sum(r["esbmc_accepted"] for r in rewrites),
                "tokens": sum(r["tokens"] for r in rewrites),
                "model": getattr(synthesizer, "model", ""),
                "token_cap": max_total_tokens,
                "not_run_budget": sum(r["rewrite_eligible"] and not r.get("rewrite") for r in records),
            } if rewrites else {}),
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
    name = "summary.json" if shards == 1 else f"summary_shard{shard}.json"
    (out / name).write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("output_dir")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--synth-backend", default="", help="enables the rewrite stage (API or CLI cost)")
    parser.add_argument("--synth-model", default="gpt-4o-mini")
    parser.add_argument("--max-total-tokens", type=int, default=None, help="stop starting rewrites past this")
    parser.add_argument("--shard", type=int, default=0)
    parser.add_argument("--shards", type=int, default=1)
    cli = parser.parse_args()
    synth = None
    if cli.synth_backend:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
        from .replay import LocalReplayExecutor
        from .synth import HarnessSynthesizer
        synth = HarnessSynthesizer(backend=cli.synth_backend, model=cli.synth_model)
    print(json.dumps(evaluate_offline(
        cli.manifest, cli.output_dir, per_case_timeout=cli.timeout, synthesizer=synth,
        executor=LocalReplayExecutor() if synth else None, max_total_tokens=cli.max_total_tokens,
        shard=cli.shard, shards=cli.shards,
    ), indent=2))
