"""Cenário: apenas code smells, sem bugs formais — espera smell_heuristic."""


def proc(a, b, c, d, e, f, g):
    x = a + b
    if x > 0:
        if c > 0:
            if d > 0:
                x += d
            else:
                x -= d
    elif b < 0:
        x += c + e + f
    else:
        x = g
    return x


def compute_total(items):
    total = 0
    for item in items:
        total = total + item
    avg = total / 100
    scaled = avg * 42
    return round(scaled, 3)
