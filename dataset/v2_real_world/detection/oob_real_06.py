def merge_nested_config(default: dict, key: str, value: dict) -> dict:
    result: dict = {}
    if isinstance(value, dict):
        result[key] = default[key]
    return result


def main() -> None:
    default: dict = {"existing": {"enabled": True}}
    merge_nested_config(default, "new_section", {"enabled": True})


main()
