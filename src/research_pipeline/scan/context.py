"""How a function is really called: its call sites in the repository, with a few lines around each."""

from __future__ import annotations

import re

from .callgraph import MODULE_CALLER, CallGraph, CallSite

NO_CALLERS = "# no call to this function was found in the repository"
MAX_SITES = 8
MAX_CHARS = 3_000


def caller_context(graph: CallGraph, key: str, *, before: int = 3, after: int = 1, max_sites: int = MAX_SITES,
                   max_chars: int = MAX_CHARS, rename: bool = True, depth: int = 1) -> str:
    """The detection prompt renames the function to ``target_function`` and the context follows suit
    (``rename``); the spec prompt names the function, so it keeps the real name. ``depth`` > 1 adds the
    callers of the callers (RepoAudit's inter-procedural context), after every direct call."""
    function = graph.functions[key]
    sites = _sites(graph, key, depth)
    if not sites:
        return NO_CALLERS
    blocks = [_block(graph, site, before, after, level) for site, level in sites[:max_sites]]
    text = ""
    shown = 0
    for block in blocks:
        if text and len(text) + len(block) + 1 > max_chars:
            break
        text = f"{text}\n{block}" if text else block[:max_chars]
        shown += 1
    if shown < len(sites):
        text += f"\n# [+{len(sites) - shown} call(s) omitted]"
    return re.sub(rf"\b{re.escape(function.name)}\b", "target_function", text) if rename else text


def _sites(graph: CallGraph, key: str, depth: int) -> list[tuple[CallSite, int]]:
    """Call sites level by level. Above the first, a caller already shown (the target, a direct caller) is left
    out and never climbed again, so recursion and cycles end."""
    found, climbed, frontier = [], {key}, [key]
    for level in range(1, depth + 1):
        sites = [site for callee in frontier for site in graph.callers(callee)
                 if level == 1 or site.caller not in climbed]
        found += [(site, level) for site in sites]
        frontier = [c for c in dict.fromkeys(site.caller for site in sites)
                    if c in graph.functions and c not in climbed]
        climbed.update(frontier)
    return found


def _block(graph: CallGraph, site: CallSite, before: int, after: int, level: int = 1) -> str:
    lines = graph.sources.get(site.file, [])
    caller = graph.functions.get(site.caller)
    low, high = site.line - before, site.end_line + after
    if caller is not None:
        # Never show the code of a neighbouring function: only the caller's own lines.
        low, high = max(low, caller.start_line), min(high, caller.end_line)
        where = f"{caller.qualname}, {site.file}"
    else:
        where = f"module level, {site.file}" if site.caller.endswith(MODULE_CALLER) else site.file
    low, high = max(low, 1), min(high, len(lines))
    via = f" (to {graph.functions[site.callee].qualname}, {level - 1} call(s) away from the target)" if level > 1 else ""
    out = [f"# call in {where}, line {site.line}{via}:"]
    if caller is not None and caller.start_line < low:
        out.append(f"{caller.start_line:>5} | {lines[caller.start_line - 1].rstrip()}")
        if caller.start_line + 1 < low:
            out.append("      | ...")
    out.extend(f"{n:>5} | {lines[n - 1].rstrip()}" for n in range(low, high + 1))
    return "\n".join(out)
