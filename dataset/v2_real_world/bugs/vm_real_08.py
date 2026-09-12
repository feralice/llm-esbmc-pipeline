def open_output_file(uses_undefined_name: bool) -> None:
    # Real code (pysnooper/pysnooper.py:get_write_function, BugsInPy
    # PySnooper bug #3): `with open(output_path, 'a') as output_file:` --
    # the enclosing function's parameter is named `output`, not
    # `output_path`. `output_path` is never defined anywhere, so this
    # raises NameError on every call.
    assert not uses_undefined_name


def main() -> None:
    uses_undefined_name: bool = nondet_bool()
    open_output_file(uses_undefined_name)


main()
