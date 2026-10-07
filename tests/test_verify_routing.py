import pytest

from research_pipeline.verify.routing import API_AGENT, CLAUDE_AGENT, DYNAMIC, route


@pytest.mark.parametrize(("verdict", "reason", "expected"), [
    ("MISSING_DEPENDENCY", "ERROR: Module 'layers' not found.", (CLAUDE_AGENT, DYNAMIC)),
    ("MISSING_DEPENDENCY", 'ERROR: Function "opfunc" not found', (CLAUDE_AGENT, DYNAMIC)),
    ("MISSING_DEPENDENCY", "ERROR: Base class not found: MutableMapping", (CLAUDE_AGENT, DYNAMIC)),
    ("SPEC_FAILED", "", (API_AGENT, CLAUDE_AGENT, DYNAMIC)),
    ("UNVALIDATED", "", (API_AGENT, CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "TypeError: __init__() takes 1 positional argument but 2 were given",
     (API_AGENT, CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "ERROR: Unsupported expression Starred at line 26", (DYNAMIC,)),
    ("UNSUPPORTED", "ERROR: unsupported: non-constant argument in str % formatting", (DYNAMIC,)),
    ("UNSUPPORTED", "external call Substitution(...) uses *args/**kwargs", (DYNAMIC,)),
    ("UNSUPPORTED", "ERROR: uncaught exception [16irep2_cast_error]: irep2", (DYNAMIC,)),
    ("GROUNDING_FAILED", "function 'rnn._step' not found (or ambiguous)", (DYNAMIC,)),
    ("ESBMC_TIMEOUT", "ESBMC direto excedeu o tempo limite de 180s.", (DYNAMIC,)),
    ("ESBMC_ERROR", "ESBMC direto: resultado inconclusivo.", (DYNAMIC,)),
    ("CONFIRMED", "", ()),
    ("NOT_CONFIRMED", "", ()),
    ("ESBMC_MISSED", "", ()),
    ("UNSUPPORTED", "something never seen before", (DYNAMIC,)),
])
def test_route(verdict, reason, expected) -> None:
    assert route({"verdict": verdict, "reason": reason}) == expected
