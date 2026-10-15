class PWMOut:
    def deinit(self):
        """Deinit the PWM."""
        self._pwmpin.stop()
        GPIO.cleanup(self._pin.id)
        self._pwmpin = None
