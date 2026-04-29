from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from research_pipeline.pipeline import run_pipeline_multi


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pipeline de pesquisa LLM + ESBMC para análise de código Python.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  # Analisar um arquivo com Claude (padrão)
  python scripts/run_research_pipeline.py examples/minimal_index_division.py

  # Analisar múltiplos arquivos com OpenAI
  python scripts/run_research_pipeline.py f1.py f2.py

  # Usar Claude com modelo específico
  python scripts/run_research_pipeline.py examples/minimal_index_division.py \\
      --llm-backend anthropic --llm-model claude-opus-4-7
        """,
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="ARQUIVO",
        help="Um ou mais arquivos Python para analisar.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(REPO_ROOT / "artifacts" / "research-pipeline"),
        help="Diretório para relatórios e arquivos instrumentados.",
    )
    parser.add_argument(
        "--esbmc-command",
        nargs="+",
        default=None,
        metavar="CMD",
        help="Comando ESBMC opcional, ex: --esbmc-command esbmc --python",
    )
    parser.add_argument(
        "--llm-backend",
        choices=["openai", "anthropic"],
        default="openai",
        help="Backend LLM. 'anthropic' usa Claude; 'openai' usa modelos OpenAI. (padrão: anthropic)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help=(
            "Modelo a usar. Padrão: 'claude-sonnet-4-6' para anthropic, 'gpt-4o' para openai. "
            "Exemplos Claude: claude-opus-4-7, claude-haiku-4-5-20251001. "
            "Exemplos OpenAI: gpt-4o, gpt-4o-mini, o1."
        ),
    )
    parser.add_argument(
        "--openai-api-key",
        default=None,
        help="Chave de API OpenAI. Se omitida, usa OPENAI_API_KEY do ambiente.",
    )
    parser.add_argument(
        "--anthropic-api-key",
        default=None,
        help="Chave de API Anthropic. Se omitida, usa ANTHROPIC_API_KEY do ambiente.",
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

    input_paths = [Path(p) for p in args.inputs]
    missing = [p for p in input_paths if not p.exists()]
    if missing:
        for p in missing:
            print(f"Erro: arquivo não encontrado: {p}", file=sys.stderr)
        return 1

    anthropic_key, openai_key = _resolve_api_keys(args)

    results = run_pipeline_multi(
        input_paths=input_paths,
        output_dir=args.output_dir,
        esbmc_command=args.esbmc_command,
        backend=args.llm_backend,
        llm_model=args.llm_model,
        openai_api_key=openai_key,
        anthropic_api_key=anthropic_key,
    )

    print(json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False))
    print(f"\nRelatório salvo em: {Path(args.output_dir) / 'report.json'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
