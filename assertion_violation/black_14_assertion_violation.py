IMPORT_AS_NAMES = 271
IMPORT_AS_NAME = 270


def get_future_imports(child_type: int, is_leaf: bool) -> None:
    if not is_leaf:
        assert child_type == IMPORT_AS_NAMES
