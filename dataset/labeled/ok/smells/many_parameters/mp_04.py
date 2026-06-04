def format_metric(value: int, minimum: int, maximum: int, warn: int, critical: int, enabled: bool) -> str:
    if not enabled:
        return "disabled"
    if value >= critical:
        return "critical"
    if value >= warn:
        return "warn"
    if value < minimum or value > maximum:
        return "range"
    return "ok"