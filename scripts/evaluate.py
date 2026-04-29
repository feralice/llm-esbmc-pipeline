from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.pipeline import run_pipeline

LABELED_DIR = REPO_ROOT / "examples" / "labeled"
GROUND_TRUTH_PATH = LABELED_DIR / "ground_truth.json"


def _verifiable_findings(findings):
    return [f for f in findings if f.verifiable]


def _matches_expected(finding, expected):
    return (
        finding.category == expected["category"]
        and finding.verifiable == expected["verifiable"]
    )


def _evaluate_file(filename: str, expected_findings: list[dict], backend: str, model: str, anthropic_api_key: str | None, openai_api_key: str | None) -> dict:
    file_path = LABELED_DIR / filename
    if not file_path.exists():
        print(f"  AVISO: {filename} não encontrado em {LABELED_DIR}", file=sys.stderr)
        return {"tp": 0, "fp": 0, "fn": len(expected_findings)}

    results = run_pipeline(
        input_path=file_path,
        output_dir=str(REPO_ROOT / "artifacts" / "research-pipeline"),
        backend=backend,
        llm_model=model,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
    )

    generated_verifiable = [r.finding for r in results if r.finding.verifiable]
    expected_verifiable = [e for e in expected_findings if e.get("verifiable")]

    print(f"\nArquivo: {filename}")

    if not expected_verifiable:
        print("  Esperado: nenhum finding verifiable")
        if not generated_verifiable:
            print("  Gerado:   nenhum finding verifiable ✓")
            return {"tp": 0, "fp": 0, "fn": 0}
        else:
            for f in generated_verifiable:
                print(f"  Gerado:   {f.category} em {f.id} (verifiable=true) ✗  [falso positivo]")
            return {"tp": 0, "fp": len(generated_verifiable), "fn": 0}

    tp = 0
    fp = 0
    fn = 0
    matched_generated = set()

    for exp in expected_verifiable:
        func_name = exp["function"]
        matched = None
        for i, gf in enumerate(generated_verifiable):
            if i in matched_generated:
                continue
            if gf.category == exp["category"]:
                matched = i
                break

        exp_label = f"{exp['category']} em {func_name} (verifiable=true)"
        if matched is not None:
            gf = generated_verifiable[matched]
            matched_generated.add(matched)
            gen_label = f"{gf.category} em {gf.id} (verifiable=true)"
            print(f"  Esperado: {exp_label}")
            print(f"  Gerado:   {gen_label} ✓")
            tp += 1
        else:
            print(f"  Esperado: {exp_label}")
            print(f"  Gerado:   (não detectado) ✗  [falso negativo]")
            fn += 1

    for i, gf in enumerate(generated_verifiable):
        if i not in matched_generated:
            print(f"  Gerado extra: {gf.category} em {gf.id} (verifiable=true) ✗  [falso positivo]")
            fp += 1

    return {"tp": tp, "fp": fp, "fn": fn}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Avalia o pipeline LLM + ESBMC contra ground truth rotulado.",
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
        choices=["openai", "anthropic"],
        default="openai",
        help="Backend LLM a usar. (padrão: anthropic)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help="Modelo a usar. Padrão depende do backend.",
    )
    parser.add_argument(
        "--anthropic-api-key",
        default=None,
        help="Chave de API Anthropic. Se omitida, usa ANTHROPIC_API_KEY do ambiente.",
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="Chave de API OpenAI. Se omitida, usa OPENAI_API_KEY do ambiente.",
    )
    return parser


def _resolve_api_keys(args: argparse.Namespace) -> tuple[str | None, str | None]:
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")

    if args.llm_backend == "anthropic" and not anthropic_key:
        print(
            "Erro: backend 'anthropic' selecionado, mas ANTHROPIC_API_KEY nao esta configurada.\n"
            "Defina a variavel de ambiente ou passe --anthropic-api-key.\n"
            "Exemplo no terminal atual:\n"
            "  export ANTHROPIC_API_KEY='sua-chave-aqui'",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if args.llm_backend == "openai" and not openai_key:
        print(
            "Erro: backend 'openai' selecionado, mas OPENAI_API_KEY nao esta configurada.\n"
            "Defina a variavel de ambiente ou passe --openai-api-key.\n"
            "Exemplo no terminal atual:\n"
            "  export OPENAI_API_KEY='sua-chave-aqui'",
            file=sys.stderr,
        )
        raise SystemExit(2)

    return anthropic_key, openai_key


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    anthropic_key, openai_key = _resolve_api_keys(args)

    _DEFAULT_MODEL = {"openai": "gpt-4o", "anthropic": "claude-sonnet-4-6"}
    model = args.llm_model or _DEFAULT_MODEL[args.llm_backend]

    if not GROUND_TRUTH_PATH.exists():
        print(f"Erro: ground truth não encontrado em {GROUND_TRUTH_PATH}", file=sys.stderr)
        return 1

    ground_truth = json.loads(GROUND_TRUTH_PATH.read_text(encoding="utf-8"))

    print("=== AVALIAÇÃO DO PIPELINE ===")
    print(f"Backend: {args.llm_backend} | Modelo: {model}")

    total_tp = 0
    total_fp = 0
    total_fn = 0

    for filename, entry in ground_truth.items():
        counts = _evaluate_file(
            filename=filename,
            expected_findings=entry.get("expected_findings", []),
            backend=args.llm_backend,
            model=model,
            anthropic_api_key=anthropic_key,
            openai_api_key=openai_key,
        )
        total_tp += counts["tp"]
        total_fp += counts["fp"]
        total_fn += counts["fn"]

    precision = total_tp / (total_tp + total_fp) if (total_tp + total_fp) > 0 else 0.0
    recall = total_tp / (total_tp + total_fn) if (total_tp + total_fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

    print("\n=== MÉTRICAS ===")
    print(f"True Positives:  {total_tp}")
    print(f"False Positives: {total_fp}  (LLM disse verifiable=true mas não deveria)")
    print(f"False Negatives: {total_fn}  (LLM não detectou bug real)")
    print(f"Precision: {precision:.0%}")
    print(f"Recall:    {recall:.0%}")
    print(f"F1:        {f1:.0%}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
