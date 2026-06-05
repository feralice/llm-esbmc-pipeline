def should_alert(cpu: int, memory: int, disk: int, degraded: bool) -> bool:
    return (cpu > 90 and memory > 80) or (disk > 95 and degraded) or (cpu > 70 and memory > 70 and disk > 70)