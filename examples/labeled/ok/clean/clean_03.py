def clamp_score(score: int) -> int:
    if score < 0:
        return 0
    if score > 100:
        return 100
    assert score >= 0 and score <= 100
    return score
