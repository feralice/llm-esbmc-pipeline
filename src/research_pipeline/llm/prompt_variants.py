"""Named changes to the V2 detection prompt, measured one at a time against the baseline."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

_DIR = Path(__file__).resolve().parents[1] / "prompts" / "v2_variants"


def _swap(name: str, prompt: str, old: str, new: str) -> str:
    if old not in prompt:
        raise ValueError(f"variant {name}: anchor not found in the V2 prompt: {old[:40]!r}")
    return prompt.replace(old, new)


def _report_without_context(prompt: str) -> str:
    prompt = _swap("A1", prompt, "`metadata.context_needed` e, quando apropriado, não reporte o achado.",
                   "`metadata.context_needed` e reporte o achado mesmo assim.")
    return _swap("A1", prompt, "`metadata.context_needed` para indicar o que falta e prefira não reportar o\nachado.",
                 "`metadata.context_needed` para indicar o que falta e reporte o achado: o\n"
                 "ESBMC e a reexecução decidem.")


def _input_checklist(prompt: str) -> str:
    checklist = (_DIR / "A2_checklist.txt").read_text(encoding="utf-8")
    return _swap("A2", prompt, "## SAÍDA: JSON válido", checklist + "\n## SAÍDA: JSON válido")


def _ranked(prompt: str) -> str:
    return _swap("A3", prompt,
                 "A saída pode conter zero, uma ou várias hipóteses: não existe quantidade mínima\n"
                 "nem máxima fixa.",
                 "Liste até 5 hipóteses por função, da mais para a menos provável de ser um bug\n"
                 "real; zero é uma resposta válida.")


VARIANTS: dict[str, Callable[[str], str]] = {"A1": _report_without_context, "A2": _input_checklist, "A3": _ranked}


def apply_variants(prompt: str, names: tuple[str, ...]) -> str:
    for name in names:
        if name not in VARIANTS:
            raise ValueError(f"unknown V2 prompt variant {name!r}; known: {sorted(VARIANTS)}")
        prompt = VARIANTS[name](prompt)
    return prompt
