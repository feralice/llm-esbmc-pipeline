def remove_upstream_option(list_len: int, idx: int) -> None:
    # Real code (thefuck/rules/git_push.py): pops `command.script_parts` at
    # the same index TWICE, assuming the upstream flag always comes with a
    # paired value ("-u origin" -> 2 tokens to remove). For `git push -u`
    # (flag with no value, list shrinks to length (list_len - 1) after the
    # first pop), the second pop(idx) can fall out of range.
    parts: list = []
    for i in range(list_len):
        parts.append(i)
    parts.pop(idx)
    parts.pop(idx)


def main() -> None:
    list_len: int = nondet_int()
    idx: int = nondet_int()
    # Real precondition: idx was found by searching the ORIGINAL list, so it
    # is valid before any pop happens.
    __ESBMC_assume(list_len >= 1 and list_len <= 4)
    __ESBMC_assume(idx >= 0 and idx < list_len)
    remove_upstream_option(list_len, idx)


main()
