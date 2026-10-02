def sorted_dict_eq(self_d: dict, that_d: dict) -> bool:
    # Real code (sortedcontainers/sorteddict.py, SortedDict.__eq__, pre-fix a04f4a68):
    # len(self._dict) == len(that) and all(self[key] == that[key] for key in self).
    # With equal lengths but different keys, that[key] raises KeyError.
    if len(self_d) != len(that_d):
        return False
    for key in self_d.keys():
        if self_d[key] != that_d[key]:
            return False
    return True


def main() -> None:
    self_d: dict = {"a": 1, "b": 2}
    that_d: dict = {"a": 1, "c": 3}
    sorted_dict_eq(self_d, that_d)


main()
