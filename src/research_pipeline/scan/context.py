"""How a function is really called: its call sites in the repository, with a few lines around each."""

from __future__ import annotations

import re

from .callgraph import MODULE_CALLER, CallGraph, CallSite

NO_CALLERS = "# nenhuma chamada a esta função foi encontrada no repositório"
MAX_SITES = 8
MAX_CHARS = 3_000


def caller_context(graph: CallGraph, key: str, *, before: int = 3, after: int = 1, max_sites: int = MAX_SITES,
                   max_chars: int = MAX_CHARS, rename: bool = True) -> str:
    """The detection prompt renames the function to ``target_function`` and the context follows suit
    (``rename``); the spec prompt names the function, so it keeps the real name."""
    function = graph.functions[key]
    sites = graph.callers(key)
    if not sites:
        return NO_CALLERS
    blocks = [_block(graph, site, before, after) for site in sites[:max_sites]]
    text = ""
    shown = 0
    for block in blocks:
        if text and len(text) + len(block) + 1 > max_chars:
            break
        text = f"{text}\n{block}" if text else block[:max_chars]
        shown += 1
    if shown < len(sites):
        text += f"\n# [+{len(sites) - shown} chamada(s) omitida(s)]"
    return re.sub(rf"\b{re.escape(function.name)}\b", "target_function", text) if rename else text


def _block(graph: CallGraph, site: CallSite, before: int, after: int) -> str:
    lines = graph.sources.get(site.file, [])
    caller = graph.functions.get(site.caller)
    low, high = site.line - before, site.end_line + after
    if caller is not None:
        # Never show the code of a neighbouring function: only the caller's own lines.
        low, high = max(low, caller.start_line), min(high, caller.end_line)
        where = f"{caller.qualname}, {site.file}"
    else:
        where = f"nível de módulo, {site.file}" if site.caller.endswith(MODULE_CALLER) else site.file
    low, high = max(low, 1), min(high, len(lines))
    out = [f"# chamada em {where}, linha {site.line}:"]
    if caller is not None and caller.start_line < low:
        out.append(f"{caller.start_line:>5} | {lines[caller.start_line - 1].rstrip()}")
        if caller.start_line + 1 < low:
            out.append("      | ...")
    out.extend(f"{n:>5} | {lines[n - 1].rstrip()}" for n in range(low, high + 1))
    return "\n".join(out)
