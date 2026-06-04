def normalize_scores(values: list[int]) -> list[int]:
    result: list[int] = []
    minimum = 0
    maximum = 0
    first = True
    for value in values:
        if first:
            minimum = value
            maximum = value
            first = False
        if value < minimum:
            minimum = value
        if value > maximum:
            maximum = value
    span = maximum - minimum
    for value in values:
        if span == 0:
            result.append(0)
        else:
            result.append((value - minimum) * 100 // span)
    return result