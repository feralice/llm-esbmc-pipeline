def buggy_merge(has_setting: bool, setting_val: int, has_override: bool, override_val: int) -> int:
    # Real code (thefuck/types.py, Settings.update, BugsInPy thefuck bug #29):
    # conf = dict(self); conf.update(kwargs) -- kwargs (overrides) always win,
    # even over settings the user already explicitly set.
    result: int = 0
    if has_setting:
        result = setting_val
    if has_override:
        result = override_val
    return result


def correct_merge(has_setting: bool, setting_val: int, has_override: bool, override_val: int) -> int:
    # Fixed version: conf = dict(kwargs); conf.update(self) -- existing
    # settings win, kwargs only fill in what was unset.
    result: int = 0
    if has_override:
        result = override_val
    if has_setting:
        result = setting_val
    return result


def main() -> None:
    has_setting: bool = nondet_bool()
    has_override: bool = nondet_bool()
    setting_val: int = nondet_int()
    override_val: int = nondet_int()
    __ESBMC_assume(has_setting and has_override and setting_val != override_val)
    assert buggy_merge(has_setting, setting_val, has_override, override_val) == \
        correct_merge(has_setting, setting_val, has_override, override_val)


main()
