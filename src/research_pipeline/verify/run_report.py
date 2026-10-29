"""One run's results as a report: confirmed bugs with their test, what the controls rejected, and what
stayed an LLM suspicion with the reason ESBMC could not decide it. Reads results only; runs nothing."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .levels import limit_group
from .outcome import CHECKED

_CONFIRMED = ("CONFIRMED",)
# ESBMC confirmed it on a body the agent changed: evidence, never a confirmed bug of the real code.
_SIMPLIFIED = ("CONFIRMED_SIMPLIFIED",)
_REJECTED = ("FIXED_ALSO_FAILS", "BEHAVIOUR_CHANGED", "STUB_INDUCED")


def _where(result: dict) -> str:
    h = result["hypothesis"]
    return f"`{Path(h['file']).name}::{h['function']}`"


def _confirmed(result: dict) -> str:
    replay, test = result.get("replay") or {}, result.get("pytest") or {}
    line = f"- {_where(result)}: `{result['hypothesis'].get('suspect_expression', '')}`"
    if replay.get("exception_type"):
        line += f" levanta `{replay['exception_type']}` com as entradas `{replay.get('inputs')}`"
    if test.get("path"):
        return line + f". Teste: `{test['path']}` ({test.get('status')})."
    return line + f". Sem teste: {test.get('reason') or 'nenhum gerado'}."


def render_run_report(results: list[dict], held: list[dict] | None = None,
                      detection: tuple[int, list[str]] | None = None) -> str:
    """``held``: findings the detection itself marked as not verifiable by ESBMC (a wrong value, the
    environment), each with ``file``, ``function``, ``expression`` and ``explanation``. ``detection``: how many
    functions were analysed and the errors of those that failed, so a failed scan never reads as a clean one."""
    confirmed = [r for r in results if r["verdict"] in _CONFIRMED]
    simplified = [r for r in results if r["verdict"] in _SIMPLIFIED]
    rejected = [r for r in results if r["verdict"] in _REJECTED]
    suspicions: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r["verdict"] not in _CONFIRMED + _SIMPLIFIED + _REJECTED:
            # A harness defect is the agent's to fix, never a limit of ESBMC.
            group = (r["verdict"] if r["verdict"] in CHECKED else
                     "harness_broken" if r["verdict"] == "HARNESS_BROKEN" else limit_group(r["verdict"], r.get("reason", "")))
            suspicions[group].append(r)
    failures = []
    if detection is not None and detection[1]:
        total, errors = detection
        failures = [f"## A detecção falhou em {len(errors)} de {total} funções", "",
                    "Essas funções não foram analisadas: o relatório abaixo não diz nada sobre elas.", "",
                    *(f"- {error[:200]}" for error in errors[:10]), ""]
    lines = ["# Relatório da rodada", "", *failures,
             (f"{len(results)} hipóteses: {len(confirmed)} confirmadas pelo ESBMC, {len(rejected)} barradas pelos "
              f"controles, {len(simplified)} confirmadas só em código simplificado, "
              f"{len(results) - len(confirmed) - len(rejected) - len(simplified)} não confirmadas (o ESBMC disse seguro, "
              "não decidiu, ou o harness não chegou a rodar)."), "",
             f"## Confirmados ({len(confirmed)})", "", *map(_confirmed, confirmed), "",
             f"## Confirmados em código simplificado ({len(simplified)})", "",
             "O agente mudou o corpo da função para o ESBMC aceitar: valem como pista, não como bug do código real.",
             "", *(f"- {_where(r)}: {r.get('reason', '')}" for r in simplified), "",
             f"## Falsos positivos barrados pelos controles ({len(rejected)})", "",
             *(f"- {_where(r)}: {r['verdict']}, {r.get('reason', '')}" for r in rejected), "",
             *([f"## Suspeitas do LLM que o ESBMC não verifica ({len(held)})", "",
                *(f"- `{Path(h['file']).name}::{h['function']}`: `{h['expression']}`. {h['explanation']}"
                  for h in held), ""] if held is not None else []),
             "## Suspeitas do LLM", ""]
    for group in sorted(suspicions):
        lines += [f"### {group} ({len(suspicions[group])})", "",
                  *(f"- {_where(r)}: {r['verdict']}, {r.get('reason', '')[:200]}" for r in suspicions[group]), ""]
    return "\n".join(lines)
