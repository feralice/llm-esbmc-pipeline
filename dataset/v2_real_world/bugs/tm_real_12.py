def read_s3_load_path(called_as_function: bool) -> None:
    # Real code (luigi/contrib/redshift.py:S3CopyToTable.copies, BugsInPy
    # luigi bug #25): `path = self.s3_load_path()`. s3_load_path is declared
    # `@abc.abstractproperty`, so accessing it already returns the load path
    # string; calling it with () tries to call that string as a function,
    # raising TypeError: 'str' object is not callable.
    assert not called_as_function


def main() -> None:
    called_as_function: bool = nondet_bool()
    read_s3_load_path(called_as_function)


main()
