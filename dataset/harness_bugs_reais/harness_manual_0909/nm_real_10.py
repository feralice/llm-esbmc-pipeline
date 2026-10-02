def insert_colnames(columns_is_none: bool, columns_len: int) -> str:
    # Real code (luigi/contrib/redshift.py:353-357, S3CopyToTable.copy):
    # `if len(self.columns) > 0:` crashes with TypeError: object of type
    # 'NoneType' has no len() when self.columns is None (the default for
    # tables without an explicit column list). Fixed to
    # `if self.columns and len(self.columns) > 0:`.
    assert not columns_is_none
    colnames: str = ''
    if not columns_is_none and columns_len > 0:
        colnames = 'cols'
    return colnames


def main() -> None:
    columns_is_none: bool = nondet_bool()
    columns_len: int = nondet_int()
    __ESBMC_assume(columns_len >= 0)
    insert_colnames(columns_is_none, columns_len)


main()
