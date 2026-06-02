from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from research_pipeline.evaluator import EvalCounts, evaluate_model, prf

GROUND_TRUTH_PATH = REPO_ROOT / "examples" / "labeled" / "ground_truths" / "bugs"

_DEFAULT_MODEL: dict[str, str] = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-6"}


def print_report(counts: EvalCounts, backend: str, model: str) -> None:
    bug_p, bug_r, bug_f1 = prf(counts.bug_tp, counts.bug_fp, counts.bug_fn)
    smell_p, smell_r, smell_f1 = prf(counts.smell_tp, counts.smell_fp, counts.smell_fn)
    all_tp = counts.bug_tp + counts.smell_tp
    all_fp = counts.bug_fp + counts.smell_fp
    all_fn = counts.bug_fn + counts.smell_fn
    ov_p, ov_r, ov_f1 = prf(all_tp, all_fp, all_fn)

    print(f"\n=== MÉTRICAS: {backend}/{model} ===")
    print(f"{'Categoria':22} {'TP':>4} {'FP':>4} {'FN':>4}  {'Precision':>10} {'Recall':>8} {'F1':>6}")
    print("-" * 64)
    print(f"{'Bugs (verifiable)':22} {counts.bug_tp:>4} {counts.bug_fp:>4} {counts.bug_fn:>4}  {bug_p:>9.0%} {bug_r:>7.0%} {bug_f1:>5.0%}")
    print(f"{'Smells (heuristic)':22} {counts.smell_tp:>4} {counts.smell_fp:>4} {counts.smell_fn:>4}  {smell_p:>9.0%} {smell_r:>7.0%} {smell_f1:>5.0%}")
    print("-" * 64)
    print(f"{'Overall':22} {all_tp:>4} {all_fp:>4} {all_fn:>4}  {ov_p:>9.0%} {ov_r:>7.0%} {ov_f1:>5.0%}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Avalia um LLM contra ground truth rotulado (bugs + smells).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/evaluate.py
  python scripts/evaluate.py --llm-backend openai --llm-model gpt-4o
  python scripts/evaluate.py --llm-backend anthropic --llm-model claude-opus-4-7
        """,
    )
    parser.add_argument(
        "--llm-backend",
        choices=["openai", "anthropic", "ollama"],
        default="anthropic",
        help="Backend LLM a usar. (padrão: anthropic)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Modelo a usar. Padrões: claude-sonnet-4-6 / gpt-4o / llama3.2.",
    )
    parser.add_argument("--anthropic-api-key", default=None)
    parser.add_argument("--openai-api-key", default=None)
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="URL base do Ollama. (padrão: http://localhost:11434/v1)",
    )
    return parser


def _resolve_keys(args: argparse.Namespace) -> tuple[str | None, str | None, str]:
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")
    model = args.llm_model or _DEFAULT_MODEL.get(args.llm_backend, args.llm_backend)

    if args.llm_backend == "anthropic" and not anthropic_key:
        print("Erro: ANTHROPIC_API_KEY não configurada. Defina no .env.", file=sys.stderr)
        raise SystemExit(2)
    if args.llm_backend == "openai" and not openai_key:
        print("Erro: OPENAI_API_KEY não configurada. Defina no .env.", file=sys.stderr)
        raise SystemExit(2)

    return anthropic_key, openai_key, model


def main() -> int:
    args = build_parser().parse_args()
    anthropic_key, openai_key, model = _resolve_keys(args)

    if not GROUND_TRUTH_PATH.exists():
        print(f"Erro: ground truth não encontrado em {GROUND_TRUTH_PATH}", file=sys.stderr)
        return 1

    print(f"=== AVALIAÇÃO DO PIPELINE ===")
    print(f"Backend: {args.llm_backend} | Modelo: {model}")

    counts = evaluate_model(
        ground_truth_path=GROUND_TRUTH_PATH,
        backend=args.llm_backend,
        model=model,
        anthropic_api_key=anthropic_key,
        openai_api_key=openai_key,
        ollama_base_url=getattr(args, "ollama_base_url", None),
        verbose=True,
    )

    print_report(counts, args.llm_backend, model)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
