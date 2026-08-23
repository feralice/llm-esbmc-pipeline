def build_recipients(to_is_list: bool) -> bool:
    # Real code (scrapy/mail.py, MailSender.send): pre-fix directly did
    # `msg['To'] = COMMASPACE.join(to)` without wrapping `to` in
    # `arg_to_iter(to)` first. When a caller passes `to` as a single email
    # address string (not a list), str.join() iterates the string
    # character by character, silently producing "a,@,b,.,c,o,m" instead
    # of the intended single address. Fixed by wrapping `to`/`cc` in
    # `arg_to_iter(...)` before joining.
    assert to_is_list
    return to_is_list


def main() -> None:
    to_is_list: bool = nondet_bool()
    build_recipients(to_is_list)


main()
