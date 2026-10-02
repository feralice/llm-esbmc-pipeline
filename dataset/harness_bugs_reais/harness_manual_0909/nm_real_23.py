def html_class_str_from_tag(html_classes_is_none: bool) -> None:
    # Real code (python-markdown2, lib/markdown2.py:Markdown._html_class_str_from_tag,
    # pre-fix, issue #391): `if tag in html_classes_from_tag:` runs unguarded
    # when self.extras["html-classes"] is explicitly None (a user can pass
    # extras={"html-classes": None}), raising `TypeError: argument of type
    # 'NoneType' is not iterable`.
    assert not html_classes_is_none


def main() -> None:
    html_classes_is_none: bool = nondet_bool()
    html_class_str_from_tag(html_classes_is_none)


main()
