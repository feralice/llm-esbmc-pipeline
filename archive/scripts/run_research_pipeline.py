from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import webbrowser
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / ".env")

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
        choices=["openai", "anthropic", "ollama"],
        default="openai",
        help="Backend LLM. 'ollama' roda modelos locais. (padrão: openai)",
    )
    parser.add_argument(
        "--llm-model",
        default=None,
        help=(
            "Modelo a usar. Padrões: 'claude-sonnet-4-6' (anthropic), 'gpt-4o' (openai), 'llama3.2' (ollama). "
            "Exemplos Ollama: llama3.2, mistral, phi3, gemma3."
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
    parser.add_argument(
        "--ollama-base-url",
        default=None,
        help="URL base do Ollama. (padrão: http://localhost:11434/v1)",
    )
    return parser


def _resolve_api_keys(args: argparse.Namespace) -> tuple[str | None, str | None]:
    anthropic_key = args.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    openai_key = args.openai_api_key or os.environ.get("OPENAI_API_KEY")

    if args.llm_backend == "anthropic" and not anthropic_key:
        print(
            "Erro: backend 'anthropic' selecionado, mas ANTHROPIC_API_KEY nao esta configurada.\n"
            "Defina no arquivo .env ou passe --anthropic-api-key.",
            file=sys.stderr,
        )
        raise SystemExit(2)

    if args.llm_backend == "openai" and not openai_key:
        print(
            "Erro: backend 'openai' selecionado, mas OPENAI_API_KEY nao esta configurada.\n"
            "Defina no arquivo .env ou passe --openai-api-key.",
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
        ollama_base_url=getattr(args, "ollama_base_url", None),
    )

    report_path = Path(args.output_dir) / "report.json"
    print(json.dumps([result.to_dict() for result in results], indent=2, ensure_ascii=False))
    print(f"\nRelatório JSON salvo em: {report_path}", file=sys.stderr)

    html_path = _generate_html(report_path)
    if html_path:
        print(f"Relatório HTML salvo em: {html_path}", file=sys.stderr)
        _open_browser(html_path)

    return 0


def _generate_html(report_path: Path) -> Path | None:
    sys.path.insert(0, str(Path(__file__).parent))
    try:
        from report_html import generate_html, _load_ground_truth  # type: ignore[import]
    except ImportError:
        return None

    report = json.loads(report_path.read_text(encoding="utf-8"))
    # Ground truth para comparação — passa vazio se o arquivo não existir.
    gt_path = REPO_ROOT / "examples" / "labeled" / "ground_truth.json"
    gt = _load_ground_truth(gt_path) if gt_path.exists() else {}
    html_path = report_path.with_suffix(".html")
    html_path.write_text(generate_html(report, str(report_path), gt), encoding="utf-8")
    return html_path


def _open_browser(path: Path) -> None:
    # WSL: converte para caminho Windows e abre com explorer
    try:
        win_path = subprocess.check_output(
            ["wslpath", "-w", str(path)], text=True
        ).strip()
        subprocess.Popen(["explorer.exe", win_path])
        return
    except Exception:
        pass
    # Fallback: webbrowser padrão
    try:
        webbrowser.open(path.as_uri())
    except Exception:
        pass


if __name__ == "__main__":
    raise SystemExit(main())
