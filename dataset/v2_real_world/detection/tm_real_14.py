def read_conllx_head(head: str, token_id: int) -> int:
    return (int(head) - 1) if head != "0" else token_id


def main() -> None:
    read_conllx_head("_", 0)


main()
