def get_begin_attr(has_begin: bool) -> str:
    attrs: dict = {}
    if has_begin:
        attrs["begin"] = "1.0s"
    return attrs["begin"]


def main() -> None:
    has_begin: bool = nondet_bool()
    get_begin_attr(has_begin)


main()
