# Regra project_decorators_removed. Origem: docs/projeto/regras_pos_congelamento_2026-10-15.patch.
def logged(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper


@logged
def ratio(k: int) -> int:
    return 10 // k


def main() -> None:
    ratio(0)


main()
