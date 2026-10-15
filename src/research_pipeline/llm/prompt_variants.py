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


def _any_wrong_behaviour(prompt: str) -> str:
    """Items 2 and 3 of the evidence test asked only about exceptions; the definition of a bug does not."""
    prompt = _swap("A6", prompt,
                   "2. Existe guarda que bloqueia EXATAMENTE o valor problemático em TODOS os caminhos?",
                   "2. Existe guarda que impede EXATAMENTE o comportamento errado em TODOS os caminhos?\n"
                   "   Comportamento errado é qualquer um: exceção, valor diferente do que o código, a\n"
                   "   docstring ou os nomes indicam, efeito indevido sobre o estado.")
    return _swap("A6", prompt,
                 "3. A exceção é capturada por try/except? Se sim, não reporte como bug que quebra.",
                 "3. O erro é tratado antes de sair da função (exceção capturada, valor corrigido)?\n"
                 "   Se sim, não reporte.")


def _reason_first(prompt: str) -> str:
    prompt = _swap("A7", prompt,
                   "Faça uma análise estruturada da função, mas não produza uma cadeia de raciocínio\ngenérica.",
                   "Antes de decidir os achados, escreva sua análise no campo `analysis`: percorra\n"
                   "cada parâmetro e cada atributo lido, e cada caminho até cada operação perigosa,\n"
                   "dizendo que valor quebra e que guarda o bloqueia ou não. Só depois preencha `findings`.")
    return _swap("A7", prompt, '{\n  "findings": [', '{\n  "analysis": "<análise caminho a caminho>",\n  "findings": [')


def _worked_examples(prompt: str) -> str:
    examples = (_DIR / "A8_exemplos.txt").read_text(encoding="utf-8")
    return _swap("A8", prompt, "## SAÍDA: JSON válido", examples + "\n## SAÍDA: JSON válido")


_CAUSE_AND_CRASH = """## ONDE O BUG NASCE E ONDE QUEBRA

Um bug que levanta exceção pode ter dois lugares: onde ele nasce (a expressão que
uma correção mudaria, em `expression`) e onde a exceção estoura (em
`crash_expression`). Exemplo: `n = len(xs) - 1` nasce o índice errado, e `xs[n + 1]`
é onde estoura. Preencha `crash_expression` com a expressão exata onde a exceção é
levantada quando ela difere de `expression`; deixe vazio quando for a mesma ou quando
nada quebra.
"""


def _cause_and_crash(prompt: str) -> str:
    prompt = _swap("A9", prompt, "## SAÍDA: JSON válido", _CAUSE_AND_CRASH + "\n## SAÍDA: JSON válido")
    return _swap("A9", prompt, '"expression": "<expressão ou statement exato copiado do código>",',
                 '"expression": "<expressão ou statement exato copiado do código>",\n'
                 '        "crash_expression": "<expressão onde a exceção estoura, ou vazio>",')


def _keep_docstring(prompt: str) -> str:
    """The base prompt already cites the docstring as evidence while the source sent drops it;
    A10 only changes the user prompt (``build_user_prompt``), which then keeps it."""
    return prompt


_FILE_CONTEXT = """## CONTEXTO DO ARQUIVO

Depois da função vem um bloco `UNTRUSTED_CONTEXT_ARQUIVO`, extraído do mesmo arquivo:
imports, a classe da função (assinaturas dos métodos e atributos de `self` criados em
`__init__`) e as funções do arquivo que a chamam, com a linha da chamada. Use-o para
decidir tipos e contratos (o que um atributo pode valer, com que argumentos a função é
chamada). Ele não é a função analisada: não reporte achados sobre ele.
"""


def _file_context(prompt: str) -> str:
    return _swap("A11", prompt, "## SAÍDA: JSON válido", _FILE_CONTEXT + "\n## SAÍDA: JSON válido")


def _repo_callers(prompt: str) -> str:
    callers = (_DIR / "A12_chamadores.txt").read_text(encoding="utf-8")
    return _swap("A12", prompt, "## SAÍDA: JSON válido", callers + "\n## SAÍDA: JSON válido")


VARIANTS: dict[str, Callable[[str], str]] = {"A1": _report_without_context, "A2": _input_checklist, "A3": _ranked,
                                             "A6": _any_wrong_behaviour, "A7": _reason_first,
                                             "A8": _worked_examples, "A9": _cause_and_crash,
                                             "A10": _keep_docstring, "A11": _file_context,
                                             "A12": _repo_callers}


def apply_variants(prompt: str, names: tuple[str, ...]) -> str:
    for name in names:
        if name not in VARIANTS:
            raise ValueError(f"unknown V2 prompt variant {name!r}; known: {sorted(VARIANTS)}")
        prompt = VARIANTS[name](prompt)
    return prompt
