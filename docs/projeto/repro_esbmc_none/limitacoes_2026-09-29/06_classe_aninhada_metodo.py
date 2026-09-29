class np:
    class random:
        @staticmethod
        def randint(a0: int) -> int:
            v: int = nondet_int()
            return v


def f(n: int) -> int:
    k: int = np.random.randint(n)
    return n // k


def main() -> None:
    n: int = nondet_int()
    f(n)


main()
