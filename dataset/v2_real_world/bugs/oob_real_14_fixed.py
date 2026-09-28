# Fix distro d3e91941: return {} when lines is empty.
def parse_uname_content(lines: list) -> str:
    if not lines:
        return ""
    return lines[0]


def main() -> None:
    lines: list = []
    parse_uname_content(lines)


main()
