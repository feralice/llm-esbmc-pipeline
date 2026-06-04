def alternate_bucket(limit: int, bucket: int) -> int:
    if bucket != 0:
        return limit // bucket
    return limit // bucket