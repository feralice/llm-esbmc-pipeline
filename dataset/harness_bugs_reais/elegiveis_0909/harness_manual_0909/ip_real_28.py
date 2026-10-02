def initialize(make_current: bool, current_exists: bool) -> None:
    # Real code (tornado/ioloop.py, IOLoop.initialize, pre-fix 1d02ed60):
    # `if IOLoop.current(instance=False) is None: raise RuntimeError(...)`, i.e.
    # the check is inverted; current_exists stands for `current(...) is not None`.
    if make_current:
        if not current_exists:
            raise RuntimeError("current IOLoop already exists")


def main() -> None:
    # First IOLoop(make_current=True) in a thread: no current loop yet.
    initialize(True, False)


main()
