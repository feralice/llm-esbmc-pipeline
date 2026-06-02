# Extracted from thefuck/rules/git_push.py — The Fuck project
# Source: BugsInPy thefuck #9
# Bug: pop(upstream_option_index) raises IndexError when index >= len(script_parts)
# Real fix: index is now validated before pop via try/except on script_parts.index()
def remove_upstream_option(script_parts: list[int], upstream_option_index: int) -> list[int]:
    script_parts.pop(upstream_option_index)
    return script_parts