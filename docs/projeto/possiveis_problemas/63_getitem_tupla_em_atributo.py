# CPython: executa sem erro (__getitem__ devolve 0, o assert passa).
# ESBMC master 4a356e33eb: SIGSEGV no encoder (Bitwuzla, smt_solver.cpp:1558, lessthan com tipos
# misturados); com --z3: "Z3 error operator is applied to arguments of the wrong sort".
# O receptor é um atributo (fr.loc); com loc: Loc = fr.loc; loc[0, 1] dá SUCCESSFUL.
# Com chave escalar (fr.loc[0]) não aborta, mas dá FAILED em __ESBMC_list_at (falso positivo).
# Reduzido de bip_pandas_162 (_normalize: table.loc[:, margins_name]).
class Loc:
    def __getitem__(self, key) -> int:
        return 0


class Frame:
    def __init__(self) -> None:
        self.loc: Loc = Loc()


fr = Frame()
assert fr.loc[0, 1] == 0
