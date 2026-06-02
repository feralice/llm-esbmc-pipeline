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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compara múltiplos LLMs contra ground truth rotulado (bugs + smells).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Comparar Claude Sonnet vs GPT-4o (padrão)
  python scripts/compare_eval.py

  # Especificar modelos
  python scripts/compare_eval.py \\
      --models anthropic:claude-sonnet-4-6 anthropic:claude-opus-4-7 openai:gpt-4o openai:gpt-4o-mini

  # Só Claude
  python scripts/compare_eval.py --models anthropic:claude-sonnet-4-6 anthropic:claude-haiku-4-5-20251001
        """,
    )
    parser.add_argument(
        "--models",
        nargs="+",
        metavar="BACKEND:MODEL",
        default=["anthropic:claude-sonnet-4-6", "openai:gpt-4o"],
        help=(
            "Modelos no formato backend:model. "
            "Ex: anthropic:claude-opus-4-7 openai:gpt-4o-mini ollama:llama3.2 ollama:mistral"
        ),
    )
    parser.add_argument("--anthropic-api-key", default=None)
    parser.add_argument("--openai-api-key", default=None)
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="URL base do Ollama para modelos locais. (padrão: http://localhost:11434/v1)",
    )
    return parser


def _resolve_keys(args: argparse.Namespace) -> tuple[str | None, str | None]:
    return (
        args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"),
        args.openai_api_key or os.environ.get("OPENAI_API_KEY"),
    )


def _parse_models(specs: list[str], anthropic_key: str | None, openai_key: str | None) -> list[tuple[str, str]]:
    parsed: list[tuple[str, str]] = []
    for spec in specs:
        if ":" not in spec:
            print(f"Erro: formato inválido '{spec}'. Use backend:model  ex: ollama:llama3.2", file=sys.stderr)
            raise SystemExit(1)
        backend, model = spec.split(":", 1)
        if backend not in ("openai", "anthropic", "ollama"):
            print(f"Erro: backend desconhecido '{backend}'. Use 'openai', 'anthropic' ou 'ollama'.", file=sys.stderr)
            raise SystemExit(1)
        if backend == "anthropic" and not anthropic_key:
            print(f"Erro: '{spec}' requer ANTHROPIC_API_KEY configurada.", file=sys.stderr)
            raise SystemExit(1)
        if backend == "openai" and not openai_key:
            print(f"Erro: '{spec}' requer OPENAI_API_KEY configurada.", file=sys.stderr)
            raise SystemExit(1)
        parsed.append((backend, model))
    return parsed


def _print_table(results: list[tuple[str, EvalCounts]]) -> None:
    W = 36
    header = (
        f"{'Modelo':{W}} | {'Bug P':>6} {'Bug R':>6} {'Bug F1':>7}"
        f" | {'Smell P':>7} {'Smell R':>7} {'Smell F1':>8}"
        f" | {'Overall F1':>10}"
    )
    sep = "-" * len(header)
    print(f"\n{'=== COMPARAÇÃO DE MODELOS ':=<{len(header)}}")
    print(header)
    print(sep)
    for name, c in results:
        bug_p, bug_r, bug_f1 = prf(c.bug_tp, c.bug_fp, c.bug_fn)
        smell_p, smell_r, smell_f1 = prf(c.smell_tp, c.smell_fp, c.smell_fn)
        all_tp = c.bug_tp + c.smell_tp
        all_fp = c.bug_fp + c.smell_fp
        all_fn = c.bug_fn + c.smell_fn
        _ov_p, _ov_r, ov_f1 = prf(all_tp, all_fp, all_fn)
        print(
            f"{name:{W}} | {bug_p:>5.0%} {bug_r:>6.0%} {bug_f1:>7.0%}"
            f" | {smell_p:>6.0%} {smell_r:>7.0%} {smell_f1:>8.0%}"
            f" | {ov_f1:>10.0%}"
        )
    print(sep)


def main() -> int:
    args = build_parser().parse_args()
    anthropic_key, openai_key = _resolve_keys(args)

    if not GROUND_TRUTH_PATH.exists():
        print(f"Erro: ground truth não encontrado em {GROUND_TRUTH_PATH}", file=sys.stderr)
        return 1

    model_specs = _parse_models(args.models, anthropic_key, openai_key)

    print(f"=== COMPARAÇÃO DE MODELOS ===")
    print(f"Ground truth: {GROUND_TRUTH_PATH}")
    print(f"Modelos a avaliar: {len(model_specs)}")

    ollama_url = getattr(args, "ollama_base_url", None)

    results: list[tuple[str, EvalCounts]] = []
    for i, (backend, model) in enumerate(model_specs, 1):
        label = f"{backend}/{model}"
        print(f"\n[{i}/{len(model_specs)}] Avaliando {label}...")
        counts = evaluate_model(
            ground_truth_path=GROUND_TRUTH_PATH,
            backend=backend,
            model=model,
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
            ollama_base_url=ollama_url,
            verbose=False,
        )
        results.append((label, counts))
        print(f"  Bugs:   TP={counts.bug_tp} FP={counts.bug_fp} FN={counts.bug_fn}")
        print(f"  Smells: TP={counts.smell_tp} FP={counts.smell_fp} FN={counts.smell_fn}")

    _print_table(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
