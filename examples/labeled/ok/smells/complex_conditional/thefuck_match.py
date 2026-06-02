# Extracted from thefuck/rules/git_push.py and related rules — The Fuck project
# Source: BugsInPy thefuck project / multiple rule match() functions
# Smell: complex conditional — match() combines script checks, error message checks,
# and command structure checks across multiple elif branches
def match(script: str, output: str, stderr: str) -> bool:
    if "git push" in script and "fatal: The current branch" in stderr:
        return True
    elif "git push" in script and "--set-upstream" not in script and "upstream" in stderr:
        return True
    elif "git push" in script and "rejected" in stderr and "non-fast-forward" in stderr:
        return True
    elif "git push" in script and "rejected" in stderr and "remote contains work" in stderr:
        return True
    elif "git push" in script and "error: failed to push" in stderr:
        return True
    else:
        return False
