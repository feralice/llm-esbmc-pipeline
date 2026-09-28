def merge_configs(default, overwrite):
    new_config = {}
    for k, v in overwrite.items():
        # Pre-fix cookiecutter/config.py: a new nested key is looked up
        # directly in default instead of using default.get(k, {}).
        if isinstance(v, dict):
            new_config[k] = merge_configs(default[k], v)
        else:
            new_config[k] = v
    return new_config


def main() -> None:
    default: dict = {"existing": {"enabled": True}}
    merge_nested_config(default, "new_section", {"enabled": True})


main()
