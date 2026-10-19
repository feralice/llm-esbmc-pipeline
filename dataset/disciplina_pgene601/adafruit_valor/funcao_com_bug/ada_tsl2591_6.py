class TSL2591:
    @property
    def lux(self):
        """Read the sensor and calculate a lux value from both its infrared
        and visible light channels.
        """
        channel_0, channel_1 = self.raw_luminosity
        # Handle overflow.
        if channel_0 == 0xFFFF or channel_1 == 0xFFFF:
            raise RuntimeError('Overflow reading light channels!')
        # Calculate lux using same equation as Arduino library:
        #  https://github.com/adafruit/Adafruit_TSL2591_Library/blob/master/Adafruit_TSL2591.cpp
        atime = 100.0 * self._integration_time + 100.0
        again = 1.0
        if self._gain == GAIN_MED:
            again = 25.0
        elif self._gain == GAIN_HIGH:
            again = 428.0
        elif self._gain == GAIN_MAX:
            again = 9876.0
        cpl = (atime * again) / _TSL2591_LUX_DF
        lux1 = (channel_0 - (_TSL2591_LUX_COEFB * channel_1)) / cpl
        lux2 = ((_TSL2591_LUX_COEFC * channel_0) - (_TSL2591_LUX_COEFD * channel_1)) / cpl
        return max(lux1, lux2)
