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
    prompt = _swap("A1", prompt, "`metadata.context_needed` and, when appropriate, do not report the finding.",
                   "`metadata.context_needed` and report the finding anyway.")
    return _swap("A1", prompt, "`metadata.context_needed` to state what is missing and prefer not to report the\nfinding.",
                 "`metadata.context_needed` to state what is missing and report the finding:\n"
                 "ESBMC and the re-execution decide.")


def _input_checklist(prompt: str) -> str:
    checklist = (_DIR / "A2_checklist.txt").read_text(encoding="utf-8")
    return _swap("A2", prompt, "## OUTPUT: valid JSON", checklist + "\n## OUTPUT: valid JSON")


def _consistency(prompt: str) -> str:
    checklist = (_DIR / "A16_consistencia.txt").read_text(encoding="utf-8")
    return _swap("A16", prompt, "## OUTPUT: valid JSON", checklist + "\n## OUTPUT: valid JSON")


def _ranked(prompt: str) -> str:
    return _swap("A3", prompt,
                 "The output may hold zero, one or several hypotheses: there is no fixed minimum\n"
                 "or maximum.",
                 "List up to 5 hypotheses per function, from the most to the least likely to be a\n"
                 "real bug; zero is a valid answer.")


def _any_wrong_behaviour(prompt: str) -> str:
    """Items 2 and 3 of the evidence test asked only about exceptions; the definition of a bug does not."""
    prompt = _swap("A6", prompt,
                   "2. Is there a guard that blocks EXACTLY the problematic value on ALL paths?",
                   "2. Is there a guard that prevents EXACTLY the wrong behaviour on ALL paths?\n"
                   "   Wrong behaviour is any of: an exception, a value different from what the code, the\n"
                   "   docstring or the names indicate, an undue effect on the state.")
    return _swap("A6", prompt,
                 "3. Is the exception caught by try/except? If so, do not report it as a bug that breaks.",
                 "3. Is the error handled before leaving the function (exception caught, value corrected)?\n"
                 "   If so, do not report it.")


def _reason_first(prompt: str) -> str:
    prompt = _swap("A7", prompt,
                   "Analyse the function in a structured way, but do not produce a generic chain of\nreasoning.",
                   "Before deciding the findings, write your analysis in the `analysis` field: go through\n"
                   "each parameter and each attribute read, and each path to each dangerous operation,\n"
                   "saying which value breaks and which guard blocks it or not. Only then fill in `findings`.")
    return _swap("A7", prompt, '{\n  "findings": [', '{\n  "analysis": "<path-by-path analysis>",\n  "findings": [')


def _worked_examples(prompt: str) -> str:
    examples = (_DIR / "A8_exemplos.txt").read_text(encoding="utf-8")
    return _swap("A8", prompt, "## OUTPUT: valid JSON", examples + "\n## OUTPUT: valid JSON")


_CAUSE_AND_CRASH = """## WHERE THE BUG STARTS AND WHERE IT BREAKS

A bug that raises an exception may have two places: where it starts (the expression a
fix would change, in `expression`) and where the exception is raised (in
`crash_expression`). Example: `n = len(xs) - 1` is where the wrong index starts, and
`xs[n + 1]` is where it breaks. Fill in `crash_expression` with the exact expression
where the exception is raised when it differs from `expression`; leave it empty when
it is the same one or when nothing breaks.
"""


def _cause_and_crash(prompt: str) -> str:
    prompt = _swap("A9", prompt, "## OUTPUT: valid JSON", _CAUSE_AND_CRASH + "\n## OUTPUT: valid JSON")
    return _swap("A9", prompt, '"expression": "<exact expression or statement copied from the code>",',
                 '"expression": "<exact expression or statement copied from the code>",\n'
                 '        "crash_expression": "<expression where the exception is raised, or empty>",')


def _keep_docstring(prompt: str) -> str:
    """The base prompt already cites the docstring as evidence while the source sent drops it;
    A10 only changes the user prompt (``build_user_prompt``), which then keeps it."""
    return prompt


_FILE_CONTEXT = """## FILE CONTEXT

After the function comes an `UNTRUSTED_CONTEXT_FILE` block, taken from the same file:
imports, the function's class (method signatures and the `self` attributes created in
`__init__`) and the functions of the file that call it, with the line of the call. Use it to
decide types and contracts (what an attribute may hold, with which arguments the function is
called). It is not the function under analysis: do not report findings about it.
"""


def _file_context(prompt: str) -> str:
    return _swap("A11", prompt, "## OUTPUT: valid JSON", _FILE_CONTEXT + "\n## OUTPUT: valid JSON")


def _repo_callers(prompt: str) -> str:
    callers = (_DIR / "A12_chamadores.txt").read_text(encoding="utf-8")
    return _swap("A12", prompt, "## OUTPUT: valid JSON", callers + "\n## OUTPUT: valid JSON")


_REAL_EXAMPLES = """## REAL BUG EXAMPLES

After the function comes an `UNTRUSTED_EXAMPLES` block with functions from other projects
and the real bug the maintainers fixed in each one: the expression the fix changed and,
when there was an exception, where it is raised. Use them to calibrate which expression to
point at in `expression`. They are not the function under analysis: do not report findings
about them and do not assume the function under analysis has the same bug.
"""


def _real_examples(prompt: str) -> str:
    """The examples themselves depend on the function; ``build_user_prompt`` adds them."""
    return _swap("A13", prompt, "## OUTPUT: valid JSON", _REAL_EXAMPLES + "\n## OUTPUT: valid JSON")


_QUOTED_EVIDENCE = """## QUOTED EVIDENCE

For each finding, fill in two more fields in `metadata`:
- `quoted_line`: the whole line of the function that holds `expression`, copied
  without changing anything; `expression` must appear inside it;
- `trigger`: the concrete condition on the inputs or the state that leads to the
  wrong behaviour, written as a Python expression over the function's names
  (for example `len(xs) == 0` or `k > len(scores)`).
If you cannot copy the line or write the condition, do not report the finding.
"""


def _quoted_evidence(prompt: str) -> str:
    prompt = _swap("A14", prompt, "## OUTPUT: valid JSON", _QUOTED_EVIDENCE + "\n## OUTPUT: valid JSON")
    return _swap("A14", prompt, '"line": 0,',
                 '"line": 0,\n'
                 '        "quoted_line": "<whole line copied from the function>",\n'
                 '        "trigger": "<condition on the inputs that leads to the error>",')


_WRONG_RESULT = """## WRONG-RESULT BUG

In `metadata.failure_mode`, say how the bug shows: `exception` when the function breaks
(exception raised or false assert), `wrong_result` when it ends normally but returns a
wrong value or leaves `self` in a wrong state, and `other` when the failure depends on the
environment. A `wrong_result` finding goes to ESBMC even with `verifiable` false: a later
step writes the property the correct result satisfies.
"""


def _wrong_result(prompt: str) -> str:
    prompt = _swap("A15", prompt, "## OUTPUT: valid JSON", _WRONG_RESULT + "\n## OUTPUT: valid JSON")
    return _swap("A15", prompt, '"context_needed": ["<helper/import/class needed, if any>"]',
                 '"context_needed": ["<helper/import/class needed, if any>"],\n'
                 '        "failure_mode": "exception | wrong_result | other"')


def _real_names(prompt: str) -> str:
    """A17 only changes the user prompt (``build_user_prompt``): the function goes as written, with its name,
    docstring and comments, which the base prompt already cites as evidence of intent."""
    return prompt


def _valid_input(prompt: str) -> str:
    """A18 sits on A5: it defines the valid input that A2's partition and the evidence test both rely on."""
    definition = (_DIR / "A18_entrada_valida.txt").read_text(encoding="utf-8")
    if "TODO(human)" in definition:
        raise ValueError("variant A18: A18_entrada_valida.txt still holds the TODO(human) placeholder")
    prompt = _swap("A18", prompt, "Each case that leads to an exception or a wrong result and passes the existing\n"
                   "guards is a hypothesis.",
                   "Each case that leads to an exception or a wrong result, passes the existing\n"
                   "guards and is a valid input (section VALID INPUT) is a hypothesis.")
    prompt = _swap("A18", prompt, "Report a bug only if the answer to item 4 is yes.",
                   "Report a bug only if the answer to item 4 is yes for a valid input.")
    return _swap("A18", prompt, "## OUTPUT: valid JSON", definition.rstrip() + "\n\n## OUTPUT: valid JSON")


_CALLEES = """## CALLED FUNCTIONS

After the function comes an `UNTRUSTED_CONTEXT_CALLEES` block with the code, comments included,
of the functions and methods of the same file that it calls. Use it to know what each call
returns and when it raises (a helper that may return None, a method that already validates the
input). It is not the function under analysis: do not report findings about it.
"""


def _callees(prompt: str) -> str:
    return _swap("A19", prompt, "## OUTPUT: valid JSON", _CALLEES + "\n## OUTPUT: valid JSON")


def _caller_slices(prompt: str) -> str:
    slices = (_DIR / "A20_fatias_chamadores.txt").read_text(encoding="utf-8")
    return _swap("A20", prompt, "## OUTPUT: valid JSON", slices + "\n## OUTPUT: valid JSON")


VARIANTS: dict[str, Callable[[str], str]] = {"A1": _report_without_context, "A2": _input_checklist, "A3": _ranked,
                                             "A6": _any_wrong_behaviour, "A7": _reason_first,
                                             "A8": _worked_examples, "A9": _cause_and_crash,
                                             "A10": _keep_docstring, "A11": _file_context,
                                             "A12": _repo_callers, "A13": _real_examples, "A14": _quoted_evidence,
                                             "A15": _wrong_result, "A16": _consistency,
                                             "A17": _real_names, "A18": _valid_input, "A19": _callees,
                                             "A20": _caller_slices}


def apply_variants(prompt: str, names: tuple[str, ...]) -> str:
    for name in names:
        if name not in VARIANTS:
            raise ValueError(f"unknown V2 prompt variant {name!r}; known: {sorted(VARIANTS)}")
        prompt = VARIANTS[name](prompt)
    return prompt
