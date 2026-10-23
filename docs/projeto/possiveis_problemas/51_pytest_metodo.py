# Gerador de pytest com método de classe (receptor).
# ESBMC master 7da3564: FAILED com ZeroDivisionError, mas o teste gerado chama `media(n)` como função solta
# (NameError no pytest). Com --no-slice chama `Conta(ctor_self, n)` com ctor_self = {} (TypeError).
class Conta:
    def __init__(self, total: int) -> None:
        self.total = total

    def media(self, n: int) -> int:
        return self.total // n


Conta(10).media(nondet_int())
