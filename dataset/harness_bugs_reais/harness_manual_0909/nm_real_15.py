def two_routes_buggy(base_has_key: bool, route1_has_key: bool, route2_has_key: bool) -> bool:
    responses = base_has_key
    responses = responses or route1_has_key
    responses = responses or route2_has_key
    return responses


def two_routes_correct(base_has_key: bool, route1_has_key: bool, route2_has_key: bool) -> bool:
    return base_has_key or route2_has_key


def main() -> None:
    base_has_key: bool = nondet_bool()
    route1_has_key: bool = nondet_bool()
    route2_has_key: bool = nondet_bool()
    buggy: bool = two_routes_buggy(base_has_key, route1_has_key, route2_has_key)
    correct: bool = two_routes_correct(base_has_key, route1_has_key, route2_has_key)
    assert buggy == correct


main()
