def proc(a, b, c, d, e, f):
    x = a + b
    if x > 0:
        if c > 0:
            x += c
        else:
            x -= c
    elif b < 0:
        x += d + e + f
    return x
