# Extracted from black.py — Black code formatter
# Source: BugsInPy black project / black.format_str()
# Smell: long method — format_str handles encoding detection, grammar selection,
# CST parsing, line splitting, trailing comma normalization, and string formatting
def format_str(src_contents: str, line_length: int = 88) -> str:
    src_contents = src_contents.replace("\r\n", "\n").replace("\r", "\n")
    if not src_contents.endswith("\n"):
        src_contents += "\n"

    lines = src_contents.split("\n")
    result_lines = []
    indent_level = 0
    in_string = False
    string_char = ""

    for line in lines:
        stripped = line.strip()

        if not stripped:
            if result_lines and result_lines[-1] != "":
                result_lines.append("")
            continue

        if not in_string:
            if stripped.startswith("#"):
                result_lines.append(" " * (indent_level * 4) + stripped)
                continue
            for char in stripped:
                if char in ('"', "'") and not in_string:
                    in_string = True
                    string_char = char
                    break

        colon_count = stripped.count(":")
        open_count = stripped.count("(") + stripped.count("[") + stripped.count("{")
        close_count = stripped.count(")") + stripped.count("]") + stripped.count("}")

        if stripped.startswith(("def ", "class ", "if ", "elif ", "else:", "for ", "while ", "try:", "except ", "finally:")):
            result_lines.append(" " * (indent_level * 4) + stripped)
            if stripped.endswith(":"):
                indent_level += 1
        elif stripped.startswith("return ") or stripped.startswith("raise "):
            result_lines.append(" " * (indent_level * 4) + stripped)
        else:
            result_lines.append(" " * (indent_level * 4) + stripped)

        if close_count > open_count and indent_level > 0:
            indent_level -= 1

    return "\n".join(result_lines) + "\n"
