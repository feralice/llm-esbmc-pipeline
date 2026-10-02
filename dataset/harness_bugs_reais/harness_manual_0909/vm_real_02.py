def validate_dict_entry(schema_is_empty: bool) -> None:
    # Real code (schema.py:Schema.validate, pre-fix, keleshev/schema): `skey`
    # is only bound inside `for skey, svalue in s.items(): ...`. When the
    # schema dict `s` is empty, that loop body never runs, so `valid` stays
    # False and the fallthrough `elif type(skey) is not Optional:` references
    # `skey` before it was ever assigned -> UnboundLocalError. skey_assigned
    # models "did the loop run at least once" (equivalent to "was s non-empty").
    skey_assigned: bool = not schema_is_empty
    valid: bool = False
    if not valid:
        assert skey_assigned


def main() -> None:
    schema_is_empty: bool = nondet_bool()
    validate_dict_entry(schema_is_empty)


main()
