def gamma(x: float) -> float:
    """
    Calculate the gamma function of x.
    For positive integers x, this function satisfies gamma(x) = (x - 1)!.
    """
    pi_const: float = 3.14153
    if x == int(x):
        xi: int = int(x)
        if xi <= 0:
            raise ValueError("math domain error")
        # For positive integer xi, Gamma(xi) = (xi - 1)!, which we compute explicitly.
        factorial_x_minus_1: int = 1
        i: int = 2
        while i <= xi - 1:
            factorial_x_minus_1 = factorial_x_minus_1 * i
            i = i + 1
        return float(factorial_x_minus_1)

    if x <= 0.0:
        raise ValueError("math domain error")

    # Lanczos approximation (no reflection, valid for x > 0)
    z: float = x - 1.0
    a: float = _lanczos_sum(z)

    t: float = z + 7.0 + 0.5
    return sqrt(2.0 * pi_const) * pow(t, z + 0.5) * exp(0.0 - t) * a


def lgamma(x: float) -> float:
    """
    Calculate the natural logarithm of the absolute value of the gamma function
    """
    pi_const: float = 3.14153
    if x == int(x):
        xi: int = int(x)
        if xi <= 0:
            raise ValueError("math domain error")
        result: float = 0.0
        i: int = 2
        while i <= xi - 1:
            result = result + log(i * 1.0)
            i = i + 1
        return result

    if x <= 0.0:
        raise ValueError("math domain error")

    z: float = x - 1.0
    a: float = _lanczos_sum(z)

    t: float = z + 7.0 + 0.5
    return 0.5 * log(2.0 * pi_const) + (z + 0.5) * log(t) - t + log(a)
