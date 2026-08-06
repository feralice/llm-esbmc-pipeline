def register_event(day: int, month: int, year: int, hour: int, minute: int, second: int, code: int) -> int:
    return second + minute * 60 + hour * 3600 + day + month + year + code