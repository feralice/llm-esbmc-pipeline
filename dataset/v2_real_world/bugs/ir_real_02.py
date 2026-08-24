def main() -> None:
    # Real code (ESBMC src/python-frontend/models/math.py, pre-#3583):
    # pi/e/tau were hardcoded to 5-6 significant digits instead of full
    # double precision, skewing every computation that used them.
    pi_buggy: float = 3.14153
    e_buggy: float = 2.71828
    tau_buggy: float = 6.28306

    assert abs(pi_buggy - 3.141592653589793) < 1e-9
    assert abs(e_buggy - 2.718281828459045) < 1e-9
    assert abs(tau_buggy - 6.283185307179586) < 1e-9


main()
