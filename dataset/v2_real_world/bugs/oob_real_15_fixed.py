# Fix youtube-dl d631d5f9: para.attrib.get('begin') and skip when missing.
def get_begin_attr(has_begin: bool) -> str:
    attrs: dict = {}
    if has_begin:
        attrs["begin"] = "1.0s"
    if "begin" not in attrs:
        return ""
    return attrs["begin"]


def main() -> None:
    has_begin: bool = nondet_bool()
    get_begin_attr(has_begin)


main()
