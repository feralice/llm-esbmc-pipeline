# Variante do 14 com a corrotina aguardada. CPython: ZeroDivisionError quando b = 0.
# ESBMC master 7da3564: AsyncFunctionDef statements are not supported. No 14 (sem await), o corpo não roda
# e o esperado é SUCCESSFUL.
import asyncio


async def ratio(a: int, b: int) -> int:
    return a // b


def main() -> None:
    a: int = nondet_int()
    b: int = nondet_int()
    asyncio.run(ratio(a, b))


main()
