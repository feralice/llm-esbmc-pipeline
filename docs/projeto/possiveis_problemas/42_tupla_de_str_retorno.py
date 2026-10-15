# CPython: ValueError quando o primeiro nondet_str() vale "bearer".
# ESBMC master: ERROR: Incompatible struct in cast-to-struct ao codificar para o Z3 (aborta, sem veredito).
def pair() -> tuple[str, str]:
    return (nondet_str(), nondet_str())


def main() -> None:
    scheme, token = pair()
    if scheme == "bearer":
        raise ValueError("bearer")


main()
