def drop_deeper(defs: list[int], depth: int) -> int:
    while len(defs) > 0 and defs[-1] >= depth:
        defs.pop()
    return 0


def main() -> None:
    defs: list[int] = nondet_list(3, elem_type=nondet_int())
    depth: int = nondet_int()
    drop_deeper(defs, depth)


main()
