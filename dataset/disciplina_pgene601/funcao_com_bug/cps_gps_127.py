def _parse_degrees(nmea_data: str) -> int:
    # Parse a NMEA lat/long data pair 'dddmm.mmmm' into a pure degrees value.
    # Where ddd is the degrees, mm.mmmm is the minutes.
    if nmea_data is None or len(nmea_data) < 3:
        return None
    # To avoid losing precision handle degrees and minutes separately
    # Return the final value as an integer. Further functions can parse
    # this into a float or separate parts to retain the precision
    raw = nmea_data.split(".")
    degrees = int(raw[0]) // 100 * 1000000  # the ddd
    minutes = int(raw[0]) % 100  # the mm.
    minutes += int(f"{raw[1][:4]:0<4}") / 10000
    minutes = int((minutes * 1000000) / 60)
    return degrees + minutes
