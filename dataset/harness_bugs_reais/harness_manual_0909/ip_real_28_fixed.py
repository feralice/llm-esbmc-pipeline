# Fix tornado 1d02ed60: raise only when a current IOLoop already exists.
def initialize(make_current: bool, current_exists: bool) -> None:
    if make_current:
        if current_exists:
            raise RuntimeError("current IOLoop already exists")


def main() -> None:
    initialize(True, False)


main()
