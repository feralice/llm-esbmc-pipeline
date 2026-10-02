def convert_float(raw_val_is_floatlike: bool) -> None:
    # Real code (python-tabulate, _format): format(float(raw_val), floatfmt)
    # crashes with ValueError/TypeError when raw_val doesn't actually
    # convert to float (e.g. bool-like strings); fix falls back to str(val).
    assert raw_val_is_floatlike


def main() -> None:
    raw_val_is_floatlike: bool = nondet_bool()
    convert_float(raw_val_is_floatlike)


main()
