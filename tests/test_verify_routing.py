import pytest

from research_pipeline.verify.routing import API_AGENT, CLAUDE_AGENT, DYNAMIC, LLM_INPUT, PINNED, route


@pytest.mark.parametrize(("verdict", "reason", "expected"), [
    ("MISSING_DEPENDENCY", "ERROR: Module 'layers' not found.", (CLAUDE_AGENT, DYNAMIC)),
    ("MISSING_DEPENDENCY", 'ERROR: Function "opfunc" not found', (CLAUDE_AGENT, DYNAMIC)),
    ("MISSING_DEPENDENCY", "ERROR: Base class not found: MutableMapping", (CLAUDE_AGENT, DYNAMIC)),
    ("SPEC_FAILED", "", (API_AGENT, CLAUDE_AGENT)),
    ("UNVALIDATED", "", (API_AGENT, CLAUDE_AGENT)),
    ("UNSUPPORTED", "TypeError: __init__() takes 1 positional argument but 2 were given",
     (API_AGENT, CLAUDE_AGENT)),
    ("UNSUPPORTED", "ERROR: Unsupported expression Starred at line 26", (DYNAMIC,)),
    ("UNSUPPORTED", "ERROR: unsupported: non-constant argument in str % formatting", (DYNAMIC,)),
    ("UNSUPPORTED", "external call Substitution(...) uses *args/**kwargs", (CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "entry point is nested inside a function; the harness cannot call it", (CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "external name 'contextmanager' is used as a decorator", (CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "stub 'obj.Config': missing return type", (CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "receiver reads inherited member(s): make_block", (CLAUDE_AGENT, DYNAMIC)),
    ("UNSUPPORTED", "ERROR: uncaught exception [16irep2_cast_error]: irep2", (DYNAMIC,)),
    ("GROUNDING_FAILED", "function 'rnn._step' not found (or ambiguous)", (CLAUDE_AGENT,)),
    ("ESBMC_TIMEOUT", "ESBMC direto excedeu o tempo limite de 180s.", (DYNAMIC, LLM_INPUT, PINNED)),
    ("UNSUPPORTED", "ERROR: Out of memory", (DYNAMIC, LLM_INPUT, PINNED)),
    ("ESBMC_ERROR", "ESBMC direto: resultado inconclusivo.", (DYNAMIC,)),
    ("CONFIRMED", "", ()),
    ("NOT_CONFIRMED", "", ()),
    ("ESBMC_MISSED", "", ()),
    ("UNSUPPORTED", "something never seen before", (CLAUDE_AGENT, DYNAMIC)),
    ("OTHER_FAILURE", "uncaught exception: AttributeError", (DYNAMIC,)),
])
def test_route(verdict, reason, expected) -> None:
    assert route({"verdict": verdict, "reason": reason}) == expected
