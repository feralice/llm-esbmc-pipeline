"""Copy the versioned part of V2 runs from artifacts/v2 (git-ignored) to docs/experimentos/fase-N/<run>/.

Keeps what an analysis needs without re-running the LLM: reports, checkpoint (the LLM's answers),
agent results, telemetry and logs, plus a resumo.json. Generated programs and harnesses stay in
artifacts/ (most of its size).

Usage:
  python scripts/archive_runs.py                 # every run listed in PHASES
  python scripts/archive_runs.py <run> --fase 9  # one new run
"""

from __future__ import annotations

import argparse
import collections
import datetime
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT / "artifacts" / "v2"
DOCS = ROOT / "docs" / "experimentos"
KEEP = ("v2_verify_report.json", "v2_report.json", "v2_checkpoint.json", "agent_results.json",
        "llm_telemetry.json", "run.log", "input_report.json", "smoke.json", "report_0of1.json",
        "replay_specs_0of1.json")

PHASES = {
    1: ["local_validation", "driver-slice-117-rerun", "end-to-end-117"],
    2: ["e2e-smoke-gpt4o-mini", "e2e-gemini-smoke", "e2e-gemini-40", "e2e-gemini-40-lite", "e2e-gemini-40-retry",
        "e2e-claude-cli-40", "e2e-gemini-40-v2", "e2e-ollama-40", "e2e-gemini-2026-09-22", "e2e-gpt-4o-mini"],
    3: ["e2e-2026-09-27-codex-single", "e2e-2026-09-27-gpt-4.1-mini-single", "e2e-2026-09-27-gpt-4o-mini-single",
        "e2e-2026-09-28-gpt-4o-mini-two-stage", "fp12-new-pipeline", "fp12-gpt4o-mini", "fp12-gpt4o-mini-rerun",
        "fp12-gpt4o-mini-full", "fp12-invalid-gpt4o-mini-fixed"],
    4: ["verify-2026-09-29-gpt-4o-mini-oracle", "verify-2026-09-29-gpt-4o-mini-oracle-r2",
        "verify-2026-09-29-gpt-4o-mini-oracle-r3", "verify-2026-09-29-gpt-4o-mini-oracle-r4",
        "verify-2026-09-29-gpt-4o-mini-oracle-r5", "agent-arm-smoke", "agent-arm-2026-09-29-oracle",
        "exp-2026-09-29-oracle-repair", "exp-oracle-repair-rep2", "exp-oracle-repair-rep3",
        "exp-2026-09-29-oracle-resample", "exp-oracle-resample-rep2", "exp-oracle-resample-rep3",
        "exp-2026-09-29-oracle-fixed", "verify-2026-09-29-gpt-4o-mini-e2e"],
    5: ["exp-oracle-repair-cobertura.pre-review", "exp-oracle-repair-cobertura", "exp-oracle-fixed-cobertura",
        "e2e-gpt-4o-mini-cobertura", "e2e-gpt-5.5-cobertura"],
    6: ["engine-2026-10-01", "engine-fixed-2026-10-01"],
    7: ["triage-2026-10-04-sonnet-20", "agent-control-fixed-2026-10-04", "triage-2026-10-04-sonnet-20-prompt2",
        "smoke-2026-10-04", "smoke-2026-10-04-esbmc", "full-2026-10-04-sonnet"],
    8: ["replay-2026-10-05-imports", "replay-2026-10-05-bases", "agent-2026-10-05-sonnet",
        "agent-2026-10-05-sonnet-reverify", "full-2026-10-05-regrounded", "control-fixed-2026-10-06",
        "replay-2026-10-06-nullrule", "agent-2026-10-06-e2e"],
}


def _verdicts(path: Path) -> dict[str, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    rows = data if isinstance(data, list) else data.get("results") or list((data.get("verify_results") or {}).values())
    return dict(collections.Counter(r.get("verdict") for r in rows if isinstance(r, dict) and r.get("verdict")))


def _summary(source: Path, kept: list[Path]) -> dict:
    summary: dict = {"pasta": source.name,
                     "modificado_em": datetime.datetime.fromtimestamp(source.stat().st_mtime).isoformat(timespec="minutes"),
                     "arquivos": sorted(p.name for p in kept)}
    checkpoint = source / "v2_checkpoint.json"
    if checkpoint.exists():
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        config = data.get("config") or {}
        summary["config"] = {k: v for k, v in config.items() if k != "input_files"}
        summary["arquivos_de_entrada"] = len(config.get("input_files", []))
        summary["status"] = data.get("status")
    for name in ("v2_verify_report.json", "agent_results.json", "report_0of1.json"):
        if (source / name).exists():
            summary[f"vereditos ({name})"] = _verdicts(source / name)
    return summary


def archive(name: str, phase: int) -> int:
    source = ARTIFACTS / name
    target = DOCS / f"fase-{phase}" / name
    target.mkdir(parents=True, exist_ok=True)
    kept = []
    if source.is_dir():
        for file_name in KEEP:
            if (source / file_name).exists():
                shutil.copy2(source / file_name, target / file_name)
                kept.append(target / file_name)
    for sibling in (ARTIFACTS / f"{name}.log", ARTIFACTS / f"{name}.json"):
        if sibling.exists():
            shutil.copy2(sibling, target / sibling.name)
            kept.append(target / sibling.name)
    if not kept:
        target.rmdir()
        print(f"fase {phase}: {name} sem arquivos para guardar")
        return 0
    if source.is_dir():
        (target / "resumo.json").write_text(json.dumps(_summary(source, kept), indent=2, ensure_ascii=False) + "\n",
                                            encoding="utf-8")
    size = sum(p.stat().st_size for p in target.iterdir())
    print(f"fase {phase}: {name} ({size / 1e6:.1f} MB)")
    return size


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run", nargs="?")
    parser.add_argument("--fase", type=int)
    args = parser.parse_args()
    if args.run:
        if args.fase is None:
            parser.error("--fase is required with a run")
        archive(args.run, args.fase)
        return 0
    total = sum(archive(name, phase) for phase, names in PHASES.items() for name in names)
    print(f"total: {total / 1e6:.1f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
