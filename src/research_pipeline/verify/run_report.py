"""One run's results as a report: confirmed bugs with their test, what the controls rejected, and what
stayed an LLM suspicion with the reason ESBMC could not decide it. Reads results only; runs nothing."""

from __future__ import annotations

import os
from collections import defaultdict
from pathlib import Path

from .levels import limit_group
from .outcome import CHECKED

_CONFIRMED = ("CONFIRMED",)
# ESBMC confirmed it on a body the agent changed: evidence, never a confirmed bug of the real code.
_SIMPLIFIED = ("CONFIRMED_SIMPLIFIED",)
# ESBMC decided nothing; CPython alone raised the exception at the suspect expression, past the same controls.
_CPYTHON = ("REPRODUCED_CPYTHON",)
_REJECTED = ("FIXED_ALSO_FAILS", "BEHAVIOUR_CHANGED", "STUB_INDUCED")


def _where(result: dict, root: str | Path | None = None) -> str:
    h = result["hypothesis"]
    return _place(h["file"], h["function"], root)


def _place(file: str, function: str, root: str | Path | None) -> str:
    # A repository has many __init__.py: under a scanned root, the path relative to it tells them apart.
    return f"`{os.path.relpath(file, root) if root else Path(file).name}::{function}`"


def evidence(result: dict) -> list[str]:
    """The checks a confirmation passed beyond ESBMC and the CPython replay, strongest audit first."""
    # Only a clean run of the fixed version counts; an unavailable one says nothing (value_oracle.apply_control).
    control, diff = result.get("control"), result.get("differential") or {}
    return [label for label, passed in (
        ("teste", (result.get("pytest") or {}).get("status") == "reproduces"),
        ("versão corrigida passa", (control or {}).get("status") == "not_reproduced"),
        ("diferencial real", diff.get("preservation") == "preservada")) if passed]


def _confirmed(result: dict, root: str | Path | None = None) -> str:
    replay, test = result.get("replay") or {}, result.get("pytest") or {}
    checks = evidence(result)
    line = (f"- {_where(result, root)}: `{result['hypothesis'].get('suspect_expression', '')}`"
            f" (evidência: {', '.join(checks) if checks else 'só ESBMC e replay' if result['verdict'] in _CONFIRMED else 'só o CPython'})")
    if replay.get("exception_type"):
        line += f" levanta `{replay['exception_type']}` com as entradas `{replay.get('inputs')}`"
    if test.get("path"):
        return line + f". Teste: `{test['path']}` ({test.get('status')})."
    return line + f". Sem teste: {test.get('reason') or 'nenhum gerado'}."


def render_run_report(results: list[dict], held: list[dict] | None = None,
                      detection: tuple[int, list[str]] | None = None, root: str | Path | None = None) -> str:
    """``held``: findings the detection itself marked as not verifiable by ESBMC (a wrong value, the
    environment), each with ``file``, ``function``, ``expression`` and ``explanation``. ``detection``: how many
    functions were analysed and the errors of those that failed, so a failed scan never reads as a clean one."""
    confirmed = sorted((r for r in results if r["verdict"] in _CONFIRMED), key=lambda r: -len(evidence(r)))
    simplified = [r for r in results if r["verdict"] in _SIMPLIFIED]
    cpython = sorted((r for r in results if r["verdict"] in _CPYTHON), key=lambda r: -len(evidence(r)))
    rejected = [r for r in results if r["verdict"] in _REJECTED]
    suspicions: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r["verdict"] not in _CONFIRMED + _SIMPLIFIED + _CPYTHON + _REJECTED:
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
              f"controles, {len(simplified)} confirmadas só em código simplificado, {len(cpython)} reproduzidas só no "
              f"CPython, {len(results) - len(confirmed) - len(rejected) - len(simplified) - len(cpython)} não confirmadas (o ESBMC disse seguro, "
              "não decidiu, ou o harness não chegou a rodar)."), "",
             f"## Confirmados ({len(confirmed)})", "",
             "Do mais para o menos verificado. Cada um passa por auditoria manual antes de virar issue.", "",
             *(_confirmed(r, root) for r in confirmed), "",
             f"## Reproduzidos só no CPython ({len(cpython)})", "",
             "O ESBMC não chegou a um veredito; o CPython levantou o erro na expressão suspeita, com o corpo original e",
             "os mesmos controles. Evidência de execução, sem prova formal.", "",
             *(_confirmed(r, root) for r in cpython), "",
             f"## Confirmados em código simplificado ({len(simplified)})", "",
             "O agente mudou o corpo da função para o ESBMC aceitar: valem como pista, não como bug do código real.",
             "", *(f"- {_where(r, root)}: {r.get('reason', '')}" for r in simplified), "",
             f"## Falsos positivos barrados pelos controles ({len(rejected)})", "",
             *(f"- {_where(r, root)}: {r['verdict']}, {r.get('reason', '')}" for r in rejected), "",
             *([f"## Suspeitas do LLM que o ESBMC não verifica ({len(held)})", "",
                *(f"- {_place(h['file'], h['function'], root)}: `{h['expression']}`. {h['explanation']}"
                  for h in held), ""] if held is not None else []),
             "## Suspeitas do LLM", ""]
    for group in sorted(suspicions):
        lines += [f"### {group} ({len(suspicions[group])})", "",
                  *(f"- {_where(r, root)}: {r['verdict']}, {r.get('reason', '')[:200]}" for r in suspicions[group]), ""]
    return "\n".join(lines)
