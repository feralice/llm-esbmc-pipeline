from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def safe_model_name(model: str) -> str:
    keep = []
    for ch in model:
        if ch.isalnum() or ch in ("-", "_"):
            keep.append(ch)
        else:
            keep.append("_")
    return "".join(keep).strip("_") or "model"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run benchmark mode for multiple LLM models.")
    parser.add_argument("--models", nargs="+", required=True, help="Models to evaluate, e.g. gpt-4o claude qwen2.5-coder:7b")
    parser.add_argument("--ground-truth", default="dataset/labeled/ground_truths")
    parser.add_argument("--output-dir", default="reports/json/benchmarks")
    parser.add_argument("--bound", type=int, default=5)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--backend", default=None, help="Optional forced backend: openai, anthropic, or ollama")
    parser.add_argument("--ollama-base-url", default=None)
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    out_dir = (ROOT / args.output_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ground_truth": str((ROOT / args.ground_truth).resolve()),
        "bound": args.bound,
        "timeout": args.timeout,
        "runs": [],
    }

    for model in args.models:
        report_path = out_dir / f"benchmark_{safe_model_name(model)}.json"
        cmd = [
            sys.executable,
            str(ROOT / "src/main.py"),
            "--mode", "benchmark",
            "--input", args.ground_truth,
            "--model", model,
            "--bound", str(args.bound),
            "--timeout", str(args.timeout),
            "--report", str(report_path),
        ]
        if args.backend:
            cmd.extend(["--backend", args.backend])
        if args.ollama_base_url:
            cmd.extend(["--ollama-base-url", args.ollama_base_url])
        if args.verbose:
            cmd.append("--verbose")

        print(f"\n=== {model} ===")
        print(" ".join(cmd))
        started = time.time()
        proc = subprocess.run(cmd, cwd=ROOT)
        elapsed = round(time.time() - started, 2)

        manifest["runs"].append({
            "model": model,
            "status": "ok" if proc.returncode == 0 else "failed",
            "returncode": proc.returncode,
            "elapsed_seconds": elapsed,
            "report": str(report_path),
        })

    manifest_path = out_dir / "benchmark_matrix_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nManifest: {manifest_path}")
    return 1 if any(run["returncode"] != 0 for run in manifest["runs"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())