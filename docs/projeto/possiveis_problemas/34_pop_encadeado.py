# CPython: KeyError ('b').
# ESBMC master: VERIFICATION SUCCESSFUL. Sem encadear (j = jobs.pop("b"); j.stop()), aborta com
# irep2_cast_error.
class Job:
    def __init__(self) -> None:
        self.n: int = 0

    def stop(self) -> int:
        return self.n


def main() -> None:
    jobs: dict[str, Job] = {"a": Job()}
    jobs.pop("b").stop()


main()
