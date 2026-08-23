def match_buggy(starts_with_sudo: bool, stderr: str) -> bool:
    return 'permission denied' in stderr.lower()


def match_correct(starts_with_sudo: bool, stderr: str) -> bool:
    if starts_with_sudo:
        return False
    return 'permission denied' in stderr.lower()


def main() -> None:
    starts_with_sudo: bool = nondet_bool()
    stderr: str = "Permission denied"
    assert match_buggy(starts_with_sudo, stderr) == match_correct(starts_with_sudo, stderr)


main()
