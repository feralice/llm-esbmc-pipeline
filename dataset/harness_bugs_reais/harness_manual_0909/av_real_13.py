def match_buggy(output: str) -> bool:
    return 'set-upstream' in output


def match_correct(output: str) -> bool:
    # Real code (thefuck/rules/git_push.py:match, BugsInPy thefuck bug #5):
    # the buggy check fires on any occurrence of the bare substring
    # "set-upstream" in git's stderr, even when it appears in an unrelated
    # message; the fix requires the full "git push --set-upstream" phrase,
    # which is what git actually prints when suggesting the fix.
    return 'git push --set-upstream' in output


def main() -> None:
    output: str = 'some other error about set-upstream mentioned here'
    b: bool = match_buggy(output)
    c: bool = match_correct(output)
    assert b == c


main()
