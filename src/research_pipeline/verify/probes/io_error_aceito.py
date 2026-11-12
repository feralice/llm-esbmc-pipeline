# Regra compat_io_error_alias. ESBMC-Python 8.6 não define IOError: o NameError vai para o reparo.
def main() -> None:
    value: int = nondet_int()
    __ESBMC_assume(value == 3)
    try:
        raise IOError(str(value))
    except OSError as error:
        assert str(error) == "3"


main()
