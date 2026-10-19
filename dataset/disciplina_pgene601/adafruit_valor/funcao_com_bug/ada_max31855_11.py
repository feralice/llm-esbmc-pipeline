class MAX31855:
    @property
    def reference_temperature(self):
        """Internal reference temperature in degrees Celsius."""
        return self._read(True) * 0.625
