# CPython: ZeroDivisionError em callee.
# ESBMC master: ERROR: Variable 'k' is not defined in function 'caller'. Com callee definida antes
# de caller, FAILED com ZeroDivisionError.
def caller(n: int) -> None:
    callee(n)


def callee(k: int) -> None:
    x = 10 // k


caller(0)
