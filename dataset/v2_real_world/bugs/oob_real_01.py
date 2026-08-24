def extract_broken_cmd(match_found: bool) -> str:
    # Real code: re.findall(r'ERROR: unknown command "([a-z]+)"', command.output)[0]
    # findall() itself isn't modeled by ESBMC-Python's re module (only
    # match/search/fullmatch are), so the list-length effect is stubbed
    # directly: `match_found` stands in for "did the narrow [a-z]+ class
    # actually match pip's real output". Real pip output can contain digits,
    # hyphens and uppercase letters in the unknown command name (e.g.
    # "instal-l", "list2"), which the buggy pattern excludes -> findall
    # returns [] -> IndexError on [0].
    matches: list = ["cmd"] if match_found else []
    return matches[0]


def main() -> None:
    match_found: bool = nondet_bool()
    extract_broken_cmd(match_found)


main()
