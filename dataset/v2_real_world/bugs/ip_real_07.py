def entity_codepoint(codepoint: int) -> str:
    # Real code (youtube_dl/utils.py:_htmlentity_transform, BugsInPy
    # youtube-dl #28): `return compat_chr(int(numstr, base))` for a numeric
    # HTML entity, uncaught. A codepoint above the valid Unicode range
    # (e.g. from `&#1114112;`, one past U+10FFFF) makes `chr()` raise
    # ValueError, which crashes the whole entity-decoding pass instead of
    # falling back to the literal `&#...;` representation.
    return chr(codepoint)


def main() -> None:
    codepoint: int = nondet_int()
    __ESBMC_assume(codepoint >= 0)
    __ESBMC_assume(codepoint <= 0x1FFFFF)
    result: str = entity_codepoint(codepoint)


main()
