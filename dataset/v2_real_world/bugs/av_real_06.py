def buggy_diff_staged(script: str) -> str:
    # Real code (thefuck/rules/git_diff_staged.py, BugsInPy thefuck bug #31):
    # appends '--staged' at the very end via .format(), regardless of where
    # trailing args (e.g. a path after `--`) sit in the command.
    return script + ' --staged'


def correct_diff_staged(script: str) -> str:
    # Fixed version: inserts '--staged' right after 'diff', not at the end.
    return script.replace(' diff', ' diff --staged')


def main() -> None:
    script: str = "git diff -- file.py"
    assert buggy_diff_staged(script) == correct_diff_staged(script)


main()
