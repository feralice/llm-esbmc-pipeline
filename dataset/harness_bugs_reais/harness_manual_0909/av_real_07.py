def buggy_match(script: str) -> bool:
    # Real code (thefuck/rules/ls_lah.py, BugsInPy thefuck bug #32):
    # 'ls' in script matches any command containing the substring 'ls',
    # e.g. 'als', not just the 'ls' command itself.
    return 'ls' in script and not ('ls -' in script)


def correct_match(script: str) -> bool:
    return (script == 'ls' or script.startswith('ls ')) and not ('ls -' in script)


def main() -> None:
    script: str = "als"
    assert buggy_match(script) == correct_match(script)


main()
