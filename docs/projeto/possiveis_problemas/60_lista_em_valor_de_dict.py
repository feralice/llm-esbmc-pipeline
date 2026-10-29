# CPython: executa sem erro (a lista guardada no dicionário recebe o item).
# ESBMC master 4a356e33eb: "ERROR: List variable not found:" (recusa).
# Só a anotação dict[str, list[str]] passa, e ela é falsa no código real (o dicionário também guarda int).
# Reduzido de bip_ansible_16 (LinuxHardware.get_cpu_facts: cpu_facts['processor'].append(...)).
d = {}
d['p'] = []
d['p'].append("x")
assert len(d['p']) == 1
