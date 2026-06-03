from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

from research_pipeline.pipeline import build_analyzer
from research_pipeline.preprocess import preprocess_file
from research_pipeline.models import Finding


def _run_analysis(file_path: Path, backend: str, model: str | None, anthropic_api_key: str | None, openai_api_key: str | None) -> dict[str, list[Finding]]:
    analyzer = build_analyzer(
        backend=backend,
        llm_model=model,
        anthropic_api_key=anthropic_api_key,
        openai_api_key=openai_api_key,
    )
    units = preprocess_file(file_path)
    result: dict[str, list[Finding]] = {}
    for unit in units:
        result[unit.qualname] = analyzer.analyze(unit)
    return result


def _finding_to_dict(f: Finding) -> dict:
    return {
        "id": f.id,
        "finding_type": f.finding_type,
        "category": f.category,
        "verifiable": f.verifiable,
        "confidence": f.confidence,
        "title": f.title,
        "explanation": f.explanation,
        "evidence": f.evidence,
        "metadata": f.metadata,
    }


def _compare_findings(
    file_path: Path,
    anthropic_findings: dict[str, list[Finding]],
    openai_findings: dict[str, list[Finding]],
) -> list[dict]:
    all_functions = set(anthropic_findings) | set(openai_findings)
    comparisons = []

    for func_name in sorted(all_functions):
        a_list = anthropic_findings.get(func_name, [])
        o_list = openai_findings.get(func_name, [])

        a_verifiable = [f for f in a_list if f.verifiable]
        o_verifiable = [f for f in o_list if f.verifiable]

        all_categories = {f.category for f in a_verifiable} | {f.category for f in o_verifiable}

        if not all_categories:
            a_heuristics = [f for f in a_list if not f.verifiable]
            o_heuristics = [f for f in o_list if not f.verifiable]
            all_categories = {f.category for f in a_heuristics} | {f.category for f in o_heuristics}

        if not all_categories:
            comparisons.append({
                "file": str(file_path),
                "function": func_name,
                "anthropic": None,
                "openai": None,
                "agreement": {
                    "both_verifiable": False,
                    "both_same_category": True,
                    "confidence_match": True,
                },
            })
            continue

        for category in sorted(all_categories):
            a_match = next((f for f in a_list if f.category == category), None)
            o_match = next((f for f in o_list if f.category == category), None)

            both_verifiable = bool(a_match and a_match.verifiable and o_match and o_match.verifiable)
            both_same_category = a_match is not None and o_match is not None and a_match.category == o_match.category
            confidence_match = (
                a_match is not None
                and o_match is not None
                and a_match.confidence == o_match.confidence
            )

            comparisons.append({
                "file": str(file_path),
                "function": func_name,
                "anthropic": _finding_to_dict(a_match) if a_match else None,
                "openai": _finding_to_dict(o_match) if o_match else None,
                "agreement": {
                    "both_verifiable": both_verifiable,
                    "both_same_category": both_same_category,
                    "confidence_match": confidence_match,
                },
            })

    return comparisons


def _print_stats(comparisons: list[dict]) -> None:
    total = len(comparisons)
    if total == 0:
        print("\nNenhum finding para comparar.")
        return

    both_verifiable = sum(1 for c in comparisons if c["agreement"]["both_verifiable"])
    same_category = sum(1 for c in comparisons if c["agreement"]["both_same_category"])
    only_anthropic = sum(1 for c in comparisons if c["anthropic"] is not None and c["openai"] is None)
    only_openai = sum(1 for c in comparisons if c["anthropic"] is None and c["openai"] is not None)

    verifiable_total = sum(
        1 for c in comparisons
        if (c["anthropic"] and c["anthropic"]["verifiable"]) or (c["openai"] and c["openai"]["verifiable"])
    )

    print("\n=== ESTATÍSTICAS DE COMPARAÇÃO ===")
    print(f"Total de findings comparados: {total}")
    print(f"Taxa de concordância em verifiable: {both_verifiable / total:.0%} ({both_verifiable}/{total})")
    print(f"Taxa de concordância em category:   {same_category / total:.0%} ({same_category}/{total})")
    print(f"Findings com verifiable em algum modelo: {verifiable_total}")
    print(f"Só Anthropic detectou:  {only_anthropic}")
    print(f"Só OpenAI detectou:     {only_openai}")
    print(f"Ambos detectaram:       {total - only_anthropic - only_openai}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compara análise de um arquivo Python entre Anthropic e OpenAI.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python scripts/compare_llms.py examples/minimal_index_division.py
  python scripts/compare_llms.py examples/labeled/div_zero_real.py \\
      --anthropic-model claude-opus-4-7 --openai-model gpt-4o-mini
        """,
    )
    parser.add_argument(
        "input",
        metavar="ARQUIVO",
        help="Arquivo Python a analisar.",
    )
    parser.add_argument(
        "--anthropic-model",
        default="claude-sonnet-4-6",
        help="Modelo Anthropic a usar. (padrão: claude-sonnet-4-6)",
    )
    parser.add_argument(
        "--openai-model",
        default="gpt-4o",
        help="Modelo OpenAI a usar. (padrão: gpt-4o)",
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

    if not anthropic_key:
        print(
            "Erro: compare_llms requer ANTHROPIC_API_KEY configurada.\n"
            "Defina a variavel de ambiente ou passe --anthropic-api-key.\n"
            "Exemplo no terminal atual:\n"
            "  export ANTHROPIC_API_KEY='sua-chave-aqui'",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if not openai_key:
        print(
            "Erro: compare_llms requer OPENAI_API_KEY configurada.\n"
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

    file_path = Path(args.input)
    if not file_path.exists():
        print(f"Erro: arquivo não encontrado: {file_path}", file=sys.stderr)
        return 1

    anthropic_key, openai_key = _resolve_api_keys(args)

    print(f"Analisando: {file_path}")
    print(f"  Anthropic: {args.anthropic_model}")
    print(f"  OpenAI:    {args.openai_model}")

    print("\n[1/2] Rodando Anthropic...")
    anthropic_findings = _run_analysis(file_path, "anthropic", args.anthropic_model, anthropic_key, openai_key)

    print("[2/2] Rodando OpenAI...")
    openai_findings = _run_analysis(file_path, "openai", args.openai_model, anthropic_key, openai_key)

    comparisons = _compare_findings(file_path, anthropic_findings, openai_findings)

    output_dir = REPO_ROOT / "artifacts" / "comparison"
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stem = file_path.stem
    report_path = output_dir / f"{stem}_{timestamp}.json"

    report = {
        "file": str(file_path),
        "anthropic_model": args.anthropic_model,
        "openai_model": args.openai_model,
        "timestamp": timestamp,
        "comparisons": comparisons,
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nRelatório salvo em: {report_path}")

    _print_stats(comparisons)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
