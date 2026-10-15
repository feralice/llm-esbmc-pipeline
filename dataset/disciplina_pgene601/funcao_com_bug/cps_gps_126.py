class GPS:
    def _update_timestamp_utc(self, time_utc: str, date: Optional[str] = None) -> None:
        hours = int(time_utc[0:2])
        mins = int(time_utc[2:4])
        secs = int(time_utc[4:6])
        if date is None:
            if self.timestamp_utc is None:
                day, month, year = 0, 0, 0
            else:
                day = self.timestamp_utc.tm_mday
                month = self.timestamp_utc.tm_mon
                year = self.timestamp_utc.tm_year
        else:
            day = int(date[0:2])
            month = int(date[2:4])
            year = 2000 + int(date[4:6])

        self.timestamp_utc = time.struct_time((year, month, day, hours, mins, secs, 0, 0, -1))
