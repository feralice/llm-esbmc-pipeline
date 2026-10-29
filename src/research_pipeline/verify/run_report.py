"""One run's results as a report: confirmed bugs with their test, what the controls rejected, and what
stayed an LLM suspicion with the reason ESBMC could not decide it. Reads results only; runs nothing."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from .levels import limit_group
from .outcome import CHECKED

_CONFIRMED = ("CONFIRMED", "CONFIRMED_SIMPLIFIED")
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


def render_run_report(results: list[dict]) -> str:
    confirmed = [r for r in results if r["verdict"] in _CONFIRMED]
    rejected = [r for r in results if r["verdict"] in _REJECTED]
    suspicions: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r["verdict"] not in _CONFIRMED + _REJECTED:
            # A harness defect is the agent's to fix, never a limit of ESBMC.
            group = (r["verdict"] if r["verdict"] in CHECKED else
                     "harness_broken" if r["verdict"] == "HARNESS_BROKEN" else limit_group(r["verdict"], r.get("reason", "")))
            suspicions[group].append(r)
    lines = ["# Relatório da rodada", "",
             (f"{len(results)} hipóteses: {len(confirmed)} confirmadas pelo ESBMC, {len(rejected)} barradas pelos "
              f"controles, {len(results) - len(confirmed) - len(rejected)} não confirmadas (o ESBMC disse seguro, "
              "não decidiu, ou o harness não chegou a rodar)."), "",
             f"## Confirmados ({len(confirmed)})", "", *map(_confirmed, confirmed), "",
             f"## Falsos positivos barrados pelos controles ({len(rejected)})", "",
             *(f"- {_where(r)}: {r['verdict']}, {r.get('reason', '')}" for r in rejected), "",
             "## Suspeitas do LLM", ""]
    for group in sorted(suspicions):
        lines += [f"### {group} ({len(suspicions[group])})", "",
                  *(f"- {_where(r)}: {r['verdict']}, {r.get('reason', '')[:200]}" for r in suspicions[group]), ""]
    return "\n".join(lines)
