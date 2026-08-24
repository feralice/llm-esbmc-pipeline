class croniter:
    @classmethod
    def _get_low_from_current_date_number(cls, field_index, step, from_timestamp):
        dt = datetime.datetime.fromtimestamp(from_timestamp, tz=UTC_DT)
        if field_index == MINUTE_FIELD:
            return dt.minute % step
        if field_index == HOUR_FIELD:
            return dt.hour % step
        if field_index == DAY_FIELD:
            return ((dt.day - 1) % step) + 1
        if field_index == MONTH_FIELD:
            return dt.month % step
        if field_index == DOW_FIELD:
            return (dt.weekday() + 1) % step

        raise ValueError("Can't get current date number for index larger than 4")
