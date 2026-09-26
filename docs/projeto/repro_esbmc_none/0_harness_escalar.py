def model() -> None:
    status: int = nondet_int()
    response_value: str = nondet_str()
    result: str = response_value
    assert result == result


model()
