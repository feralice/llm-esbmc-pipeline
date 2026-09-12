def merge_nested_config(default_has_key: bool) -> None:
    # Pre-fix cookiecutter/config.py (issue #1513): a nested key that is new
    # in the override is indexed in default unconditionally.
    assert default_has_key


def main() -> None:
    merge_nested_config(False)


main()
