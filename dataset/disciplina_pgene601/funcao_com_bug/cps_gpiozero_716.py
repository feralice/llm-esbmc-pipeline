class CPUTemperature:
    def __init__(self, sensor_file='/sys/class/thermal/thermal_zone0/temp',
            min_temp=0.0, max_temp=100.0, threshold=80.0):
        self.sensor_file = sensor_file
        super(CPUTemperature, self).__init__()
        self.min_temp = min_temp
        self.max_temp = max_temp
        self.threshold = threshold
        self._fire_events()

    @property
    def value(self):
        """
        Returns the current CPU temperature as a value between 0.0
        (representing the *min_temp* value) and 1.0 (representing the
        *max_temp* value). These default to 0.0 and 100.0 respectively, hence
        :attr:`value` is :attr:`temperature` divided by 100 by default.
        """
        temp_range = self.max_temp - self.min_temp
        return (self.temperature - self.min_temp) / temp_range
