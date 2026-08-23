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
    is_stash_command(script)


main()
