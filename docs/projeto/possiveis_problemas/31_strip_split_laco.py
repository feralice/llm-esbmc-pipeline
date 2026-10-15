# CPython: executa sem erro.
# ESBMC master: não termina em 120 s. Sem o laço (só strip e split) termina em 7 s; o laço sem o split
# interno termina em 4 s.
def main() -> None:
    out = nondet_str().strip().split("\n")
    for line in out:
        parts = line.split(" ", 1)


main()
