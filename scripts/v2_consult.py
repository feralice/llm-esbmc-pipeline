"""Ask Claude Code (the user's settings + the ESBMC plugin, the agent arm's restricted tools) why the engine
stopped on each hypothesis of a verify report; the answer is C/<id>/opiniao.md. Cases that already have
an opiniao.md are skipped, so a run resumes.

  python scripts/v2_consult.py artifacts/v2/teste-ab-2026-10-22/mini_report.json \
      --out artifacts/v2/teste-ab-2026-10-22/C

Uses the Claude Code subscription (claude -p), one session per case.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from research_pipeline.verification.esbmc_runner import DEFAULT_ESBMC  # noqa: E402
from research_pipeline.verify.agent_arm import claude_agent  # noqa: E402
from research_pipeline.verify.hypothesis import BugHypothesis  # noqa: E402
from research_pipeline.verify.loop import verification_source  # noqa: E402

_HARNESS = """- harness_pipeline.py: o harness que nosso pipeline montou automaticamente para o ESBMC.
- erro_esbmc.txt: o erro com que o ESBMC recusou esse harness."""
_REFUSED = """- recusa.txt: o motivo com que o pipeline recusou o caso antes de montar qualquer harness (não há
  harness_pipeline.py: o ESBMC nunca rodou)."""
_WHY_HARNESS = "Por que o ESBMC recusou: limitação do ESBMC (candidata a issue) ou defeito do harness do pipeline?"
_WHY_REFUSED = ("Por que o pipeline recusou antes do harness: o caso está mesmo fora do que o ESBMC-Python aceita "
                "(candidato a issue) ou é uma limitação do pipeline?")
PROMPT = """Você é consultor de verificação com ESBMC-Python. Nesta pasta:
- original.py: código real de produção com um bug suspeito na função `{function}`.
{files}
Hipótese do bug: expressão `{expression}`; condição: {trigger}

Use o plugin do ESBMC (skill esbmc-verification, /esbmc-plugin:verify, /esbmc-plugin:audit) e rode
`{esbmc} <arquivo> --unwind 5 --multi-property` sempre que ajudar. Investigue de verdade, rodando o ESBMC.
Depois escreva opiniao.md, em português, sem usar travessão, respondendo:
1. {why} Mostre a evidência.
2. Como você faria o código rodar no ESBMC sem mudar o comportamento no caminho do bug. Se conseguir, salve
   harness_consultor.py (corpo da função `{function}` igual ao original; só driver, entradas nondet e stubs
   mínimos) e diga o veredito que o ESBMC deu.
3. Que regra geral o pipeline deveria aprender com este caso (uma ou duas frases).
"""


def prepare_case(result: dict, case_dir: Path, *, sources: Path | None, root: Path, esbmc: str) -> str:
    """Write the case's files and return its prompt. A case refused before any harness (no attempt kept a
    program) gets the original and the refusal only."""
    h = BugHypothesis(**{k: v for k, v in result["hypothesis"].items() if k != "hypothesis_id"})
    case_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(root / verification_source(h, sources), case_dir / "original.py")
    built = [a for a in result.get("attempts") or [] if a.get("replay_program_path")]
    if built:
        program = built[-1]["replay_program_path"].replace("_replay.py", ".py")
        shutil.copy(root / program, case_dir / "harness_pipeline.py")
        (case_dir / "erro_esbmc.txt").write_text(f"{result['reason']}\n\n{built[-1].get('message', '')}",
                                                 encoding="utf-8")
    else:
        (case_dir / "recusa.txt").write_text(f"{result['verdict']}: {result['reason']}\n", encoding="utf-8")
    return PROMPT.format(function=h.function, expression=h.suspect_expression, trigger=h.trigger_condition,
                         esbmc=esbmc, files=_HARNESS if built else _REFUSED,
                         why=_WHY_HARNESS if built else _WHY_REFUSED)


def consult(results: list[dict], out: Path, agent, *, sources: Path | None, root: Path, esbmc: str,
            timeout_seconds: int) -> list[str]:
    """Returns the ids consulted in this run."""
    consulted = []
    for result in results:
        case_dir = out / result["hypothesis"]["hypothesis_id"]
        if (case_dir / "opiniao.md").exists():
            continue
        prompt = prepare_case(result, case_dir, sources=sources, root=root, esbmc=esbmc)
        print("consultor:", result["hypothesis"]["hypothesis_id"], result["hypothesis"]["function"], flush=True)
        try:
            text = agent(prompt, case_dir, timeout_seconds)
        except subprocess.TimeoutExpired:
            text = "TIMEOUT"
        (case_dir / "saida_claude.txt").write_text(text, encoding="utf-8")
        print("   opiniao.md:", (case_dir / "opiniao.md").exists(), flush=True)
        consulted.append(result["hypothesis"]["hypothesis_id"])
    return consulted


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("report", help="verify report (results with hypothesis, verdict, reason, attempts)")
    parser.add_argument("--out", required=True, help="one folder per case is created here")
    parser.add_argument("--verification-sources", default="dataset/bugs_reais/arquivo_com_bug")
    parser.add_argument("--esbmc", default=DEFAULT_ESBMC)
    parser.add_argument("--model", default="claude-sonnet-5-5")
    parser.add_argument("--timeout", type=int, default=1500)
    args = parser.parse_args(argv)
    results = json.loads(Path(args.report).read_text(encoding="utf-8"))["results"]
    agent = claude_agent(model=args.model, esbmc=args.esbmc, plugin=True, isolated=False)
    consult(results, Path(args.out), agent, sources=Path(args.verification_sources) if args.verification_sources
            else None, root=ROOT, esbmc=args.esbmc, timeout_seconds=args.timeout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
