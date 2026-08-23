def dicts_equal_buggy(self_d: dict, that_d: dict) -> bool:
    for key in self_d.keys():
        if self_d[key] != that_d[key]:
            return False
    return True


def main() -> None:
    self_d: dict = {"a": 1, "b": 2}
    that_d: dict = {"a": 1}
    dicts_equal_buggy(self_d, that_d)


main()
