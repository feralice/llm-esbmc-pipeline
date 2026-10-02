def buggy_emits_removal(key_in_to_remove: bool) -> bool:
    # Real code (lib/ansible/module_utils/network/eos/config/vlans/vlans.py:
    # generate_commands, BugsInPy ansible #7): every key in `to_remove` got
    # a "no <key>" command unconditionally, even when that same key was
    # also present in `to_set` (being re-applied in the same run), so the
    # generated command list removed a setting it was about to re-add.
    return key_in_to_remove


def correct_emits_removal(key_in_to_remove: bool, key_in_to_set: bool) -> bool:
    return key_in_to_remove and (not key_in_to_set)


def main() -> None:
    key_in_to_remove: bool = nondet_bool()
    key_in_to_set: bool = nondet_bool()
    __ESBMC_assume(key_in_to_remove)
    b: bool = buggy_emits_removal(key_in_to_remove)
    c: bool = correct_emits_removal(key_in_to_remove, key_in_to_set)
    assert b == c


main()
