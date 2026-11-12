"""Terminal entry point: ``llm-esbmc scan <pasta>``. Translates the arguments into the pipeline's own flags.

Without ``--yes`` the scan only simulates: it selects the functions and writes the plan, with no LLM call.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from research_pipeline.cli_args import REPO_ROOT

BACKENDS = {
    "claude": ["--backend", "claude_cli", "--agent-backend", "claude"],
    "codex": ["--backend", "codex", "--agent-backend", "codex"],
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llm-esbmc",
        description="Pipeline LLM + ESBMC para bugs de runtime em Python.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    scan = commands.add_parser(
        "scan",
        help="escaneia uma pasta de código Python (sem --yes, só simula)",
        description="Escaneia uma pasta. Sem --yes, só seleciona as funções e grava o plano, sem chamar a LLM.",
    )
    scan.add_argument("folder", help="pasta com o código Python")
    scan.add_argument("--backend", choices=sorted(BACKENDS), default="claude",
                      help="assinatura que roda o scan (padrão: claude)")
    scan.add_argument("--limit", type=int, metavar="N", help="máximo de funções (ex.: 5 para um teste)")
    scan.add_argument("--focus", default="", help="foco em texto livre")
    scan.add_argument("--out", type=Path, metavar="PASTA",
                      help="pasta de saída (padrão: artifacts/cli/<backend>/<nome da pasta>)")
    scan.add_argument("--yes", action="store_true",
                      help="gasta a cota: chamadas à LLM e agente que tenta confirmar cada hipótese com ESBMC")
    return parser


def scan_argv(args: argparse.Namespace) -> list[str]:
    folder = Path(args.folder).resolve()
    out = args.out or REPO_ROOT / "artifacts" / "cli" / args.backend / folder.name
    argv = ["--mode", "scan", "--input", str(folder), "--output-dir", str(out),
            *BACKENDS[args.backend], "--scan-rank", "pagerank"]
    if args.focus:
        argv += ["--scan-focus", args.focus]
    if args.limit is not None:
        argv += ["--scan-limit", str(args.limit)]
    if args.yes:
        argv += ["--yes", "--scan-verify", "agent"]
    return argv


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    import main as pipeline  # src/main.py: a editable install keeps it importable

    sys.argv = ["llm-esbmc", *scan_argv(args)]
    return pipeline.main()


if __name__ == "__main__":
    raise SystemExit(main())
