def table_exists(stdout: str, table: str) -> bool:
    # Real code (luigi/contrib/hive.py:HiveCommandClient.table_exists,
    # BugsInPy luigi #28): Hive normalizes table names to lowercase in its
    # `show tables` output, but the buggy substring check compared against
    # the caller's table name as-is, so a differently-cased real table was
    # reported as not existing.
    return bool(stdout) and table in stdout


def main() -> None:
    # Hive's own output is already lowercase; the caller asks about the
    # table using its real (possibly mixed-case) name.
    stdout: str = "mytable"
    table: str = "MyTable"
    result: bool = table_exists(stdout, table)
    assert result


main()
