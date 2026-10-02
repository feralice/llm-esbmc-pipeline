# esbmc: --unwind 6 --timeout 150s
# Fix sortedcontainers a04f4a68: (key in that) and (self[key] == that[key]).
def sorted_dict_eq(self_d: dict, that_d: dict) -> bool:
    if len(self_d) != len(that_d):
        return False
    for key in self_d.keys():
        if key not in that_d:
            return False
        if self_d[key] != that_d[key]:
            return False
    return True


def main() -> None:
    self_d: dict = {"a": 1, "b": 2}
    that_d: dict = {"a": 1, "c": 3}
    sorted_dict_eq(self_d, that_d)


main()
