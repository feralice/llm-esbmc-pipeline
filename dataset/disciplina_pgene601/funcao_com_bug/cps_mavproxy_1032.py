class FakeGPSModule:
    def idle_task(self):
        '''called on idle'''
        now = time.time()
        if now - self.last_send < 1.0 / self.FakeGPS_settings.rate:
            return
        self.last_send = now
        gps_lat = self.FakeGPS_settings.lat
        gps_lon = self.FakeGPS_settings.lon
        gps_alt = self.FakeGPS_settings.alt
        gps_vel = [0, 0, 0]

        gps_week, gps_week_ms = self.get_gps_time(now)

        time_us = int(now*1.0e6)

        nsats = self.FakeGPS_settings.nsats
        if nsats >= 6:
            fix_type = 3
        else:
            fix_type = 1
        self.master.mav.gps_input_send(time_us, 0, 0, gps_week_ms, gps_week, fix_type,
                                       int(gps_lat*1.0e7), int(gps_lon*1.0e7), gps_alt,
                                       1.0, 1.0,
                                       gps_vel[0], gps_vel[1], gps_vel[2],
                                       0.2, 1.0, 1.0,
                                       nsats,
                                       int(self.FakeGPS_settings.yaw*100))
