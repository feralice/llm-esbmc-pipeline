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


def _consistency(prompt: str) -> str:
    checklist = (_DIR / "A16_consistencia.txt").read_text(encoding="utf-8")
    return _swap("A16", prompt, "## SAÍDA: JSON válido", checklist + "\n## SAÍDA: JSON válido")


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


_REAL_EXAMPLES = """## EXEMPLOS DE BUGS REAIS

Depois da função vem um bloco `UNTRUSTED_EXEMPLOS` com funções de outros projetos
e o bug real que os mantenedores corrigiram em cada uma: a expressão que a correção
mudou e, quando houve exceção, onde ela estoura. Use-os para calibrar que expressão
apontar em `expression`. Eles não são a função analisada: não reporte achados sobre
eles e não suponha que a função analisada tenha o mesmo bug.
"""


def _real_examples(prompt: str) -> str:
    """The examples themselves depend on the function; ``build_user_prompt`` adds them."""
    return _swap("A13", prompt, "## SAÍDA: JSON válido", _REAL_EXAMPLES + "\n## SAÍDA: JSON válido")


_QUOTED_EVIDENCE = """## EVIDÊNCIA CITADA

Para cada achado, preencha mais dois campos em `metadata`:
- `quoted_line`: a linha inteira da função onde está `expression`, copiada sem
  mudar nada; `expression` precisa aparecer dentro dela;
- `trigger`: a condição concreta sobre as entradas ou o estado que leva ao
  comportamento errado, escrita como expressão Python sobre os nomes da função
  (por exemplo `len(xs) == 0` ou `k > len(scores)`).
Se não conseguir copiar a linha ou escrever a condição, não reporte o achado.
"""


def _quoted_evidence(prompt: str) -> str:
    prompt = _swap("A14", prompt, "## SAÍDA: JSON válido", _QUOTED_EVIDENCE + "\n## SAÍDA: JSON válido")
    return _swap("A14", prompt, '"line": 0,',
                 '"line": 0,\n'
                 '        "quoted_line": "<linha inteira copiada da função>",\n'
                 '        "trigger": "<condição sobre as entradas que leva ao erro>",')


_WRONG_RESULT = """## BUG DE RESULTADO ERRADO

Em `metadata.failure_mode`, diga como o bug aparece: `excecao` quando a função quebra
(exceção levantada ou assert falso), `resultado_errado` quando ela termina normalmente mas
devolve um valor errado ou deixa `self` num estado errado, e `outro` quando a falha depende
do ambiente. Um achado `resultado_errado` vai ao ESBMC mesmo com `verifiable` false: uma
etapa seguinte escreve a propriedade que o resultado correto cumpre.
"""


def _wrong_result(prompt: str) -> str:
    prompt = _swap("A15", prompt, "## SAÍDA: JSON válido", _WRONG_RESULT + "\n## SAÍDA: JSON válido")
    return _swap("A15", prompt, '"context_needed": ["<helper/import/classe necessária, se houver>"]',
                 '"context_needed": ["<helper/import/classe necessária, se houver>"],\n'
                 '        "failure_mode": "excecao | resultado_errado | outro"')


VARIANTS: dict[str, Callable[[str], str]] = {"A1": _report_without_context, "A2": _input_checklist, "A3": _ranked,
                                             "A6": _any_wrong_behaviour, "A7": _reason_first,
                                             "A8": _worked_examples, "A9": _cause_and_crash,
                                             "A10": _keep_docstring, "A11": _file_context,
                                             "A12": _repo_callers, "A13": _real_examples, "A14": _quoted_evidence,
                                             "A15": _wrong_result, "A16": _consistency}


def apply_variants(prompt: str, names: tuple[str, ...]) -> str:
    for name in names:
        if name not in VARIANTS:
            raise ValueError(f"unknown V2 prompt variant {name!r}; known: {sorted(VARIANTS)}")
        prompt = VARIANTS[name](prompt)
    return prompt
