# Regra nondet_clock. Gêmeo seguro de relogio_inicial: duas leituras nunca voltam no tempo.
import time


def elapsed() -> float:
    first = time.time()
    return time.time() - first


assert elapsed() >= 0.0
