import math


def _lanczos_sum(z: float) -> float:
    a: float = 0.99999999999980993
    a = a + 676.5203681218851 / (z + 1.0)
    a = a + -1259.1392167224028 / (z + 2.0)
    a = a + 771.3234287776531 / (z + 3.0)
    a = a + -176.6150291621406 / (z + 4.0)
    a = a + 12.507343278686905 / (z + 5.0)
    a = a + -0.13857109526572012 / (z + 6.0)
    a = a + 0.000009984369578019572 / (z + 7.0)
    a = a + 0.00000015056327351493116 / (z + 8.0)
    return a


def gamma_buggy(x: float) -> float:
    # Real code (ESBMC src/python-frontend/models/math.py, pre-#5963):
    # pi_const = 3.14153 is wrong in the 5th decimal place, skewing every
    # non-integer gamma() result by ~1.8e-5.
    pi_const: float = 3.14153
    z: float = x - 1.0
    a: float = _lanczos_sum(z)
    t: float = z + 7.0 + 0.5
    return math.sqrt(2.0 * pi_const) * math.pow(t, z + 0.5) * math.exp(0.0 - t) * a


def main() -> None:
    r: float = gamma_buggy(0.5)
    # Correct: gamma(0.5) == sqrt(pi) == 1.7724538509055159
    assert math.fabs(r - 1.7724538509055159) < 1e-6


main()
