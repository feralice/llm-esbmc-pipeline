# Fix spacy 9fa9d7f2: head not in ["0", "_"] before int(head).
def compute_head(head: str, id_: int) -> int:
    return (int(head) - 1) if head not in ["0", "_"] else id_


def main() -> None:
    id_: int = 5
    is_underscore: bool = nondet_bool()
    head: str = "_" if is_underscore else "0"
    compute_head(head, id_)


main()
