from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.pipeline import run_pipeline


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prototype LLM + ESBMC research pipeline for Python code."
    )
    parser.add_argument("input", help="Path to a Python file to analyze.")
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "artifacts" / "research-pipeline"),
        help="Directory for reports and instrumented files.",
    )
    parser.add_argument(
        "--esbmc-command",
        nargs="+",
        default=None,
        help="Optional ESBMC command, for example: --esbmc-command esbmc --python",
    )
    parser.add_argument(
        "--llm-backend",
        choices=["mock", "openai"],
        default="mock",
        help="LLM backend to use. 'mock' keeps the pipeline offline; 'openai' calls a real model.",
    )
    parser.add_argument(
        "--llm-model",
        default="gpt-5.4",
        help="Model name used when --llm-backend openai is selected.",
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="Optional API key. If omitted, OPENAI_API_KEY is used.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    results = run_pipeline(
        input_path=args.input,
        output_dir=args.output_dir,
        esbmc_command=args.esbmc_command,
        llm_backend=args.llm_backend,
        llm_model=args.llm_model,
        openai_api_key=args.openai_api_key,
    )
    print(json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False))
    print(f"Report saved to {Path(args.output_dir) / 'report.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
