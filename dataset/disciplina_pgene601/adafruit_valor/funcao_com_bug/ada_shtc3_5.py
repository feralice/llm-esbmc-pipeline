class SHTC3:
    @property
    def measurements(self):
        """both `temperature` and `relative_humidity`, read simultaneously"""

        self.sleeping = False
        temperature = None
        humidity = None
        # send correct command for the current power state
        if self.low_power:
            self._write_command(_SHTC3_LOWPOW_MEAS_TFIRST)
            time.sleep(0.001)
        else:
            self._write_command(_SHTC3_NORMAL_MEAS_TFIRST)
            time.sleep(0.013)

        # self._buffer = bytearray(6)
        # read the measured data into our buffer
        with self.i2c_device as i2c:
            i2c.readinto(self._buffer)

        # separate the read data
        temp_data = self._buffer[0:2]
        temp_crc = self._buffer[2]
        humidity_data = self._buffer[3:5]
        humidity_crc = self._buffer[5]

        # check CRC of bytes
        if temp_crc != self._crc8(temp_data) or humidity_crc != self._crc8(
            humidity_data
        ):
            return (temperature, humidity)

        # decode data into human values:
        # convert bytes into 16-bit signed integer
        # convert the LSB value to a human value according to the datasheet
        raw_temp = unpack_from(">h", temp_data)[0]
        raw_temp = ((4375 * raw_temp) >> 14) - 4500
        temperature = raw_temp / 100.0

        # repeat above steps for humidity data
        raw_humidity = unpack_from(">H", humidity_data)[0]
        raw_humidity = (625 * raw_humidity) >> 12
        humidity = raw_humidity / 100.0

        self.sleeping = True
        return (temperature, humidity)
