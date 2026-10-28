# CPython: executa sem erro (com o fallback, s = "a b" e len(s) = 3).
# ESBMC master 4a356e33eb: aborta com "ERROR: uncaught exception [St13runtime_error]: Unexpected index type
# in computer_pointer_offset", com e sem --no-pointer-check --no-align-check.
# Com s local em f, s global concreto, ou len(s) no nível do módulo, não aborta; s.split() também aborta.
# Reduzido de bip_thefuck_4 (a saída do fish é global e é lida dentro de Popen.__init__ no harness).
try:
    from esbmc import nondet_str
except ImportError:
    def nondet_str() -> str:
        return "a b"


def f() -> None:
    len(s)


s: str = nondet_str()
f()
