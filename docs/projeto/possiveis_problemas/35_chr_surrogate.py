# CPython: chr() aceita qualquer código de 0 a 0x10FFFF, inclusive surrogates; executa sem erro.
# ESBMC master: FAILED (chr() arg is a surrogate code point), falso positivo. Com chr(0xD800) literal,
# recusa o programa (Code point 0xD800 is a surrogate pair, invalid in UTF-8).
def main() -> None:
    n = nondet_int()
    if 0xD800 <= n <= 0xDFFF:
        c = chr(n)


main()
