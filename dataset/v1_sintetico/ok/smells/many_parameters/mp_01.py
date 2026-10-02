def create_user_record(user_id: int, age: int, score: int, region: int, role: int, active: bool) -> int:
    return user_id + age + score + region + role + (1 if active else 0)