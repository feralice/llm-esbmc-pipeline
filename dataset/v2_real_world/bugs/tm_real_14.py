def convert_head_is_safe(head_is_underscore: bool) -> None:
    # Pre-fix spaCy/converters/conllu2json.py (BugsInPy spaCy bug #4):
    # a valid CONLL-U placeholder "_" reaches int(head) in the buggy branch.
    assert not head_is_underscore


def main() -> None:
    convert_head_is_safe(True)


main()
