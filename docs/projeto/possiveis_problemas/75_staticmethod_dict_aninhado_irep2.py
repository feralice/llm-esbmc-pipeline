# CPython: executa sem erro.
# ESBMC master 822227ff96 (08/11/2026): "uncaught exception [16irep2_cast_error] ... struct_union_member_names()
# called on incompatible type (type_id = pointer)". Precisa de @staticmethod e do dict aninhado; a função solta dá SUCCESSFUL.
# NÃO é a #10121 (aberta), que é a anotação entre aspas "Optional[...]". Achado em cps_ros2cli_370 (ros2cli).
class C:
    @staticmethod
    def interfaces() -> dict[str, dict[str, str]]:
        return {"a": {}}

def f() -> None:
    for name, iface in C.interfaces().items():
        x = iface.get('flags')

f()
