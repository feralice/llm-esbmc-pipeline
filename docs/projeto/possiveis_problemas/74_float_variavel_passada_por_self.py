# CPython: executa sem erro.
# ESBMC master 822227ff96 (08/11/2026): "ESBMC caught SIGSEGV: this is an internal error".
# Parecido com a #9841 (fechada pela #9860, que tipa o parâmetro a partir de um LITERAL passado por self).
# Aqui o argumento é uma variável float. Com `tnow: float` anotado, ou com função solta, dá SUCCESSFUL.
# Achado em cps_mavproxy_1032 (MAVProxy, get_gps_time).
class M:
    def get_time(self, tnow):
        return int(tnow - 1.5)

    def idle(self):
        now: float = 0.0
        w = self.get_time(now)

M().idle()
