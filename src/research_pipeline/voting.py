from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path

VoteKey = tuple[str, str, str]


def aggregate_votes(
    model_report_dirs: Iterable[str | Path],
    min_votes: int = 2,
) -> dict:
    """Aggregate model findings by ``(file, function, category)``.

    Each input directory represents one model and must contain the ``*_eval.json``
    files produced by the benchmark's ``per_file`` reporting. Repeated findings
    from the same model count as one vote, so verbosity cannot inflate consensus.
    Ground-truth verdicts are intentionally ignored: voting uses only
    ``generated_bugs`` and is therefore safe to run before evaluation.
    """
    report_dirs = [Path(path) for path in model_report_dirs]
    if not report_dirs:
        raise ValueError("at least one model report directory is required")
    if not 1 <= min_votes <= len(report_dirs):
        raise ValueError("min_votes must be between 1 and the number of models")

    model_names = [_model_name(path) for path in report_dirs]
    if len(set(model_names)) != len(model_names):
        raise ValueError("model report directories must have distinct names")

    voters: dict[VoteKey, set[str]] = defaultdict(set)
    evidence: dict[VoteKey, dict[str, list[dict]]] = defaultdict(dict)
    files_read: dict[str, int] = {}

    for model, report_dir in zip(model_names, report_dirs):
        if not report_dir.is_dir():
            raise FileNotFoundError(f"model report directory not found: {report_dir}")

        report_files = sorted(report_dir.glob("*_eval.json"))
        if not report_files:
            raise ValueError(f"no *_eval.json files found in {report_dir}")
        files_read[model] = len(report_files)

        for report_file in report_files:
            payload = _read_report(report_file)
            source_file = str(payload.get("file") or "").strip()
            if not source_file:
                raise ValueError(f"missing file field in {report_file}")

            findings_by_key: dict[VoteKey, list[dict]] = defaultdict(list)
            generated = payload.get("generated_bugs", [])
            if not isinstance(generated, list):
                raise ValueError(f"generated_bugs must be a list in {report_file}")

            for finding in generated:
                if not isinstance(finding, dict):
                    raise ValueError(f"generated_bugs entries must be objects in {report_file}")
                function = str(finding.get("function") or "").strip()
                category = str(finding.get("category") or "").strip()
                if not function or not category:
                    raise ValueError(
                        f"generated bug missing function/category in {report_file}"
                    )
                key = (source_file, function, category)
                findings_by_key[key].append(_finding_evidence(finding))

            for key, model_evidence in findings_by_key.items():
                voters[key].add(model)
                evidence[key][model] = model_evidence

    candidates = []
    for key in sorted(voters):
        source_file, function, category = key
        agreeing_models = sorted(voters[key])
        votes = len(agreeing_models)
        candidates.append(
            {
                "file": source_file,
                "function": function,
                "category": category,
                "votes": votes,
                "models": agreeing_models,
                "selected": votes >= min_votes,
                "evidence_by_model": {
                    model: evidence[key][model] for model in agreeing_models
                },
            }
        )

    return {
        "model_count": len(report_dirs),
        "models": sorted(model_names),
        "min_votes": min_votes,
        "files_read_by_model": dict(sorted(files_read.items())),
        "candidate_count": len(candidates),
        "selected_count": sum(candidate["selected"] for candidate in candidates),
        "candidates": candidates,
    }


def write_vote_report(report: dict, output_path: str | Path) -> Path:
    """Write an aggregated vote report as deterministic UTF-8 JSON."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    return path


def _model_name(report_dir: Path) -> str:
    name = report_dir.name.strip()
    if not name:
        raise ValueError(f"cannot infer model name from {report_dir}")
    return name


def _read_report(path: Path) -> dict:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read report {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"report must contain a JSON object: {path}")
    return payload


def _finding_evidence(finding: dict) -> dict:
    return {
        key: finding[key]
        for key in ("expression", "line", "confidence")
        if key in finding
    }
