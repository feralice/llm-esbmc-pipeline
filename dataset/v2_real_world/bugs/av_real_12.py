def match_buggy(script: str) -> bool:
    return "php -s" in script


def match_correct(script: str) -> bool:
    # Real code (thefuck/rules/php_s.py:match, BugsInPy thefuck bug #7):
    # the buggy version only matched the literal substring "php -s", missing
    # any command where other flags separate "php" from "-s" (e.g.
    # "php -d foo -s bar"); the fix checks for the bare " -s " flag token
    # anywhere in the script instead.
    return " -s " in script


def main() -> None:
    script: str = "php -d foo -s bar"
    b: bool = match_buggy(script)
    c: bool = match_correct(script)
    assert b == c


main()
