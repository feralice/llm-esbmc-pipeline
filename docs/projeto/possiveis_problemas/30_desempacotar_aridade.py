# CPython: ValueError (not enough values to unpack) quando parts tem um elemento.
# ESBMC master: FAILED com out-of-bounds read in list (list.c), sem ValueError. Com elementos a mais
# (h, m = "a:b:c".split(":")) dá VERIFICATION SUCCESSFUL.
def main() -> None:
    parts: list[int] = [1]
    if nondet_bool():
        parts.append(2)
    a, b = parts


main()
