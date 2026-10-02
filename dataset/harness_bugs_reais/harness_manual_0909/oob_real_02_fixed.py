# Fix thefuck 213791d3: check len(script.split()) > 1 before indexing [1].
def is_stash_command(script: str) -> bool:
    tokens = script.split()
    if len(tokens) > 1:
        return tokens[1] == "stash"
    return False


def main() -> None:
    script: str = nondet_str()
    __ESBMC_assume(len(script) <= 10)
    is_stash_command(script)


main()
