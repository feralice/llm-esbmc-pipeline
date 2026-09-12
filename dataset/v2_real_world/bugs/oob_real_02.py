def is_stash_command(script: str) -> bool:
    # Real code (thefuck/rules/git_fix_stash.py): command.script.split()[1]
    # == 'stash'. Crashes with IndexError when the script has fewer than 2
    # whitespace-separated tokens (e.g. plain "git" with no subcommand,
    # which is exactly the kind of malformed/incomplete command this rule
    # is supposed to be robust against).
    tokens = script.split()
    return tokens[1] == "stash"


def main() -> None:
    script: str = nondet_str()
    # Bounded so ESBMC-Python's split()/strcmp internals can be fully
    # unwound at --unwind 6; unbounded nondet_str() otherwise hits the
    # string-library's own unwinding-assertion limit before reaching the
    # real is_stash_command property (see audit finding, 2026-09-11).
    __ESBMC_assume(len(script) <= 10)
    is_stash_command(script)


main()
