def buggy_replace(full_path: str, dest_dir_path: str, src_dir_path: str) -> str:
    return full_path.replace(dest_dir_path, src_dir_path)


def correct_replace(full_path: str, dest_dir_path: str, src_dir_path: str) -> str:
    return src_dir_path + full_path[len(dest_dir_path):]


def main() -> None:
    dest_dir_path: str = "a/a"
    src_dir_path: str = "b"
    full_path: str = "a/a/a/a"
    buggy: str = buggy_replace(full_path, dest_dir_path, src_dir_path)
    correct: str = correct_replace(full_path, dest_dir_path, src_dir_path)
    assert buggy == correct


main()
