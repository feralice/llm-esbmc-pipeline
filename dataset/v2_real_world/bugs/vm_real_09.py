def length_without_total(total_is_defined: bool) -> None:
    # Pre-fix tqdm/_tqdm.py (__len__, PyBugHive issue #539): when the
    # iterable has no __len__ and no explicit total was supplied, the final
    # branch reads self.total even though __init__ never created it.
    assert total_is_defined


def main() -> None:
    length_without_total(False)


main()
