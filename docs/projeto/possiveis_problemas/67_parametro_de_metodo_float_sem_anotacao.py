# CPython: executa sem erro (int(2.5 - 1.5) == 1).
# ESBMC master 0945ac9: "ESBMC caught SIGSEGV" (exit 139) com Bitwuzla; com --z3, "Z3 error rm and fp sorts expected".
# Gatilho: parâmetro de método sem anotação, chamado por self.g(...) de outro método, numa conta com float
# dentro de int(...). Com "tnow: float", ou chamando M().g(2.5) no módulo, dá o veredito certo.
# Sem contorno genérico: o harness teria de inferir o tipo do parâmetro de um método auxiliar.
# Reduzido de cps_mavproxy_1032 (FakeGPSModule.get_gps_time(self, tnow), chamado por idle_task);
# os 5 SIGSEGV da rodada Codex PGENE601 de 03/11 estão todos nesse arquivo.
class M:
    def g(self, tnow):
        return int(tnow - 1.5)

    def run(self):
        return self.g(2.5)


assert M().run() == 1
