# Regra nondet_clock. O modelo do ESBMC começa o relógio em 0.0 (models/time.py); o relógio real, não.
import time


def started() -> float:
    return time.time()


assert started() < 1.0
