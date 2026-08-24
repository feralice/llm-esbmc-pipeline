def build_params_str_buggy(significant: bool, value: int) -> dict:
    result: dict = {}
    if significant:
        result["p"] = value
    return result


def build_params_str_fixed(significant: bool, value: int) -> dict:
    result: dict = {}
    result["p"] = value
    return result


def main() -> None:
    significant: bool = False
    value: int = 5
    buggy: dict = build_params_str_buggy(significant, value)
    correct: dict = build_params_str_fixed(significant, value)
    assert buggy == correct


main()
