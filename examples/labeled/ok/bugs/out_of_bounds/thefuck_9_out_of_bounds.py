def remove_upstream_option(script_parts: list[int], upstream_option_index: int) -> list[int]:
    script_parts.pop(upstream_option_index)
    return script_parts