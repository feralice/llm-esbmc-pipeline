# Extracted from black.py — Black code formatter
# Source: BugsInPy black #17
# Bug: src_txt[-1] raises IndexError when src_txt is an empty string
# Real fix: changed to src_txt[-1:] != "\n" (slice never raises on empty string)
def lib2to3_parse(src_txt: str) -> str:
    if src_txt[-1] != "\n":
        src_txt += "\n"
    return src_txt
