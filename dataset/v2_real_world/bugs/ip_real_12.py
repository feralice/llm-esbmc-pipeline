def buggy_should_update_state(state_needs_update: bool, vrf_needs_update: bool) -> bool:
    # Real code (ansible/lib/ansible/modules/network/eos/eos_eapi.py:map_obj_to_commands,
    # BugsInPy ansible bug #15): the guard was
    # `if needs_update('state') and not needs_update('vrf'):`, so a state change
    # was silently skipped whenever vrf also needed updating in the same call.
    return state_needs_update and not vrf_needs_update


def correct_should_update_state(state_needs_update: bool, vrf_needs_update: bool) -> bool:
    # Fix drops the `and not needs_update('vrf')` guard entirely.
    return state_needs_update


def main() -> None:
    state_needs_update: bool = nondet_bool()
    vrf_needs_update: bool = nondet_bool()
    buggy: bool = buggy_should_update_state(state_needs_update, vrf_needs_update)
    correct: bool = correct_should_update_state(state_needs_update, vrf_needs_update)
    assert buggy == correct


main()
