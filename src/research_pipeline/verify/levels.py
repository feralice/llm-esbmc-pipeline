"""Which level decided each hypothesis: the deterministic engine, the agent, or the LLM alone.

ESBMC first, through the engine's harness; when that reaches no ESBMC verdict, through the agent's;
otherwise the hypothesis keeps only the LLM's finding, with the reason grouped so the limits of
ESBMC-Python on real code can be counted.
"""

from __future__ import annotations

import re
from collections import Counter

from .agent_arm import AGENT_FAILED, CONFIRMED_SIMPLIFIED
from .outcome import (
    CHECKED,
    ESBMC_ERROR,
    ESBMC_TIMEOUT,
    GROUNDING_FAILED,
    NO_SOURCE,
    PIPELINE_ERROR,
    SPEC_FAILED,
)

ENGINE, AGENT, LLM_ONLY = "esbmc_engine", "esbmc_agent", "llm_only"
# The agent simplified the function for ESBMC; ESBMC's inputs then broke the original under CPython.
SIMPLIFIED = "esbmc_agent_simplified"

# Why a hypothesis stayed with the LLM alone.
CONTEXT = "harness_context"      # what surrounds the function: names, library stubs, input types
LANGUAGE = "esbmc_language"      # a Python feature the function itself uses and ESBMC-Python lacks
CRASH = "esbmc_crash"            # ESBMC or its solver failed internally
TIMEOUT = "esbmc_timeout"
SPEC = "llm_spec"                # the LLM gave no valid input types
LOCATE = "locate_function"       # the function or its source file was not found
NETWORK = "network"
PIPELINE = "pipeline_error"      # the pipeline itself failed on this hypothesis
REWRITE = "agent_rewrote_function"
OTHER = "other"                  # a reason no rule recognises: kept apart, never counted as an ESBMC limit
LIMIT_GROUPS = (CONTEXT, LANGUAGE, CRASH, TIMEOUT, SPEC, LOCATE, NETWORK, PIPELINE, REWRITE, OTHER)
_DEEPER = (LANGUAGE, CRASH, TIMEOUT, REWRITE)

_CRASH = re.compile(r"uncaught exception \[|json\.exception|Bitwuzla error|irep2|inconclusivo|inconclusive"
                    r"|Segmentation|core dumped")
_LANGUAGE = re.compile(r"__class__|__dict__|__name__|nested attribute|Call result|Starred|% formatting"
                       r"|not yet supported|NumPy|numpy|async|Type inference failed|Cannot infer type"
                       r"|Could not resolve type|Can't generate zero|Unsupported expression|DictComp"
                       r"|del on subscript|sorted\(\) with key|'kwargs'|\"kwargs\"|Couldn't convert|unsupported:")
_NETWORK = re.compile(r"Remote|Connection|handshake|timed out|Network|rede|SSL", re.IGNORECASE)
_CONTEXT = re.compile(r"undefined name|not found|not defined|NameError|Base class|not subscriptable"
                      r"|list indices must|Cannot unpack|type mismatch|cannot determine the length"
                      r"|no-untyped|missing \d+ required positional|takes \d+ positional|unpacks (it|its result)"
                      r"|input type outside|cannot be stubbed|uses \*args|used as a decorator|external "
                      r"|inherited member|sliced verbatim")


def limit_group(verdict: str, reason: str) -> str:
    """Group of a verdict that carries no ESBMC result (one not in CHECKED)."""
    if verdict in (GROUNDING_FAILED, NO_SOURCE):
        return LOCATE
    if verdict == SPEC_FAILED:
        return SPEC
    if verdict == PIPELINE_ERROR:
        return NETWORK if _NETWORK.search(reason) else PIPELINE
    if verdict == ESBMC_TIMEOUT:
        return TIMEOUT
    if verdict == ESBMC_ERROR or _CRASH.search(reason):
        return CRASH
    if _LANGUAGE.search(reason):
        return LANGUAGE
    if _CONTEXT.search(reason):
        return CONTEXT
    return OTHER


def consolidate(engine: list[dict], agent: list[dict] | None = None) -> list[dict]:
    """One row per engine result: the level that reached an ESBMC verdict, or why none did.

    An agent result counts only for a hypothesis the engine left without a verdict. When neither
    level got one, the agent's reason wins if it reached a deeper limit (language, crash, timeout):
    it shows the context around the function was not the obstacle."""
    by_id = {a["hypothesis"]["hypothesis_id"]: a for a in agent or []}
    # A run may list one hypothesis twice (the 2026-09-30 report has 9 repeats): count it once,
    # keeping the occurrence that reached an ESBMC verdict.
    unique: dict[str, dict] = {}
    for result in engine:
        key = result["hypothesis"]["hypothesis_id"]
        if key not in unique or (result["verdict"] in CHECKED and unique[key]["verdict"] not in CHECKED):
            unique[key] = result
    rows = []
    for result in unique.values():
        hypothesis = result["hypothesis"]
        row = {"hypothesis_id": hypothesis["hypothesis_id"], "file": hypothesis["file"],
               "function": hypothesis["function"], "engine_verdict": result["verdict"]}
        tried = by_id.get(hypothesis["hypothesis_id"])
        if result["verdict"] in CHECKED:
            row.update(level=ENGINE, verdict=result["verdict"], reason=result.get("reason", ""))
        elif tried is not None and tried["verdict"] == CONFIRMED_SIMPLIFIED:
            row.update(level=SIMPLIFIED, verdict=CONFIRMED_SIMPLIFIED, reason=tried.get("reason", ""),
                       agent_verdict=tried["verdict"])
        elif tried is not None and tried["verdict"] in CHECKED and tried.get("target_preserved") is not False:
            row.update(level=AGENT, verdict=tried["verdict"], reason=tried.get("reason", ""), agent_verdict=tried["verdict"])
        else:
            group = limit_group(result["verdict"], result.get("reason", ""))
            reason = result.get("reason", "")
            if tried is not None:
                row["agent_verdict"] = tried["verdict"]
            if tried is not None and tried["verdict"] != AGENT_FAILED:
                # A verdict on a rewritten function says nothing about the original one.
                deeper = (REWRITE if tried.get("target_preserved") is False
                          else limit_group(tried["verdict"], tried.get("reason", "")))
                if deeper in _DEEPER:
                    group, reason = deeper, tried.get("reason", "")
            row.update(level=LLM_ONLY, verdict=result["verdict"], reason=reason, limit=group)
        rows.append(row)
    return rows


def level_summary(rows: list[dict]) -> dict:
    checked = [r for r in rows if r["level"] in (ENGINE, AGENT)]
    return {
        "hypotheses": len(rows),
        "by_level": dict(Counter(r["level"] for r in rows)),
        "esbmc_verdict": len(checked),
        "confirmed": sum(1 for r in checked if r["verdict"] == "CONFIRMED"),
        "confirmed_by_level": dict(Counter(r["level"] for r in checked if r["verdict"] == "CONFIRMED")),
        "confirmed_simplified": sum(1 for r in rows if r["level"] == SIMPLIFIED),
        "llm_only_by_limit": {group: sum(1 for r in rows if r.get("limit") == group) for group in LIMIT_GROUPS},
    }
