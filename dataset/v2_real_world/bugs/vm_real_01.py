def pick_bar_halves(l_bar: str, r_bar: str, l_bar_user: str, r_bar_user: str) -> str:
    # Real code (tqdm/_tqdm.py:format_meter, BugsInPy tqdm bug #8): after
    # splitting a user-supplied bar_format into l_bar_user/r_bar_user, the
    # buggy line formats the STALE l_bar/r_bar (computed earlier from the
    # default template) instead of the freshly split user halves, so a
    # custom bar_format is silently ignored.
    picked_l = l_bar
    picked_r = r_bar
    return picked_l + picked_r


def main() -> None:
    l_bar: str = input()
    r_bar: str = input()
    l_bar_user: str = input()
    r_bar_user: str = input()
    __ESBMC_assume(l_bar != l_bar_user)
    result: str = pick_bar_halves(l_bar, r_bar, l_bar_user, r_bar_user)
    assert result == l_bar_user + r_bar_user


main()
