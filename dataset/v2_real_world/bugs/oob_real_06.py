def is_stash_command(script: str) -> bool:
    # Real code (thefuck/rules/git_fix_stash.py:match, BugsInPy thefuck bug #21):
    # `command.script.split()[1] == 'stash'` crashes with IndexError when the
    # script has fewer than 2 whitespace-separated tokens (e.g. a bare "git"
    # with no subcommand at all) -- the fix adds a length guard before
    # indexing. Same shape as oob_real_02 (thefuck bug #9), different real bug.
    parts = script.split()
    return parts[1] == 'stash'


def main() -> None:
    script: str = nondet_str()
    __ESBMC_assume(len(script) <= 6)
    is_stash_command(script)


main()
