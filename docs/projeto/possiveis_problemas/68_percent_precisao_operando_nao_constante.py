# CPython: executa sem erro ("v %.1f" % 2.5 == "v 2.5").
# ESBMC master 0945ac9: "ERROR: unsupported: non-constant argument in str % formatting".
# "%f" % x e "%.1f" % 2.5 (constante) funcionam; só a precisão com operando não constante é recusada.
# f"{x:.1f}" funciona, mas o compat.py só pode trocar quando prova que o operando é numérico; nos casos
# MAVProxy os operandos vêm de stubs e subscritos. Reduzido de cps_mavproxy_1380 (' %.1fm' % (terrain_height,)).
x: float = 2.5
s = "v %.1f" % x
assert s == "v 2.5"
