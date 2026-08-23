def unlink_middle(next_is_none: bool) -> None:
    # Real code (lib/ansible/modules/system/pamd.py:478-480, PamdService.remove):
    # unlinking a doubly-linked PamdRule list did
    # `current_line.next.prev = current_line.prev` unconditionally whenever
    # current_line.prev is not None, crashing with AttributeError:
    # 'NoneType' object has no attribute 'prev' when current_line is the
    # last node in the list (current_line.next is None). Fixed to guard:
    # `if current_line.next is not None: current_line.next.prev = ...`.
    assert not next_is_none


def main() -> None:
    next_is_none: bool = nondet_bool()
    unlink_middle(next_is_none)


main()
