# CPython: TypeError (can only concatenate list (not "tuple") to list).
# ESBMC master: VERIFICATION SUCCESSFUL. Com t parâmetro e len(x) depois, aborta com
# "Unexpected type in int/ptr typecast".
def main() -> None:
    t = (nondet_int(), nondet_int())
    x = [1] + t


main()
