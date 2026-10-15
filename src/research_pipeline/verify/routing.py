"""Which arms to try after the deterministic harness, by why it stopped. Rules are classes of
reasons, never cases of the dataset."""

from __future__ import annotations

import re

DYNAMIC = "dynamic"
API_AGENT = "api_agent"
CLAUDE_AGENT = "claude_agent"
PINNED = "pinned"
LLM_INPUT = "llm_input"

_DONE = {"CONFIRMED", "NOT_CONFIRMED", "ESBMC_MISSED"}
# Context outside the function: an agent that can open the project may supply it.
_CONTEXT = re.compile(r"not found|undefined name", re.I)
# The harness itself was wrong: rewriting it is enough.
_HARNESS = re.compile(r"TypeError: .*(?:positional argument|unexpected keyword|missing \d+ required)", re.I)
# ESBMC's own refusals; any other UNSUPPORTED reason is the code-built harness giving up, which an
# agent writing the harness by hand can get past.
_ESBMC = re.compile(r"^ERROR:|uncaught exception \[|^ESBMC direto")

_ROUTES = {
    "done": (),
    "context": (CLAUDE_AGENT, DYNAMIC),
    # Replaying a harness already judged wrong would only rerun its mistake.
    "harness": (API_AGENT, CLAUDE_AGENT),
    "builder": (CLAUDE_AGENT, DYNAMIC),
    # No program exists to replay.
    "grounding": (CLAUDE_AGENT,),
    "esbmc_limit": (DYNAMIC,),
    # ESBMC accepts the program but the formula is too big: a crashing input found by the search, or
    # proposed by an LLM when the search finds none, lets it check that one path.
    "solver": (DYNAMIC, LLM_INPUT, PINNED),
}


def limit_class(result: dict) -> str:
    verdict, reason = result["verdict"], result.get("reason", "")
    if verdict in _DONE:
        return "done"
    if verdict == "ESBMC_TIMEOUT" or "Out of memory" in reason:
        return "solver"
    if verdict in {"SPEC_FAILED", "UNVALIDATED"} or _HARNESS.search(reason):
        return "harness"
    if verdict == "MISSING_DEPENDENCY" or (verdict == "UNSUPPORTED" and _CONTEXT.search(reason)):
        return "context"
    if verdict == "GROUNDING_FAILED":
        return "grounding"
    if verdict == "UNSUPPORTED" and not _ESBMC.search(reason):
        return "builder"
    return "esbmc_limit"


def route(result: dict) -> tuple[str, ...]:
    return _ROUTES[limit_class(result)]
