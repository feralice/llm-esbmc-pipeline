def compute_head(head: str, id_: int) -> int:
    # Real code (spacy/cli/converters/conllu2json.py:read_conllx, BugsInPy
    # spacy #4): CoNLL-U marks "no head token" with either "0" or the
    # universal empty-field sentinel "_". The buggy check only special-cased
    # "0", so a real "_" field reached int("_"), which raises ValueError.
    return (int(head) - 1) if head != "0" else id_


def main() -> None:
    id_: int = 5
    is_underscore: bool = nondet_bool()
    head: str = "_" if is_underscore else "0"
    compute_head(head, id_)


main()
