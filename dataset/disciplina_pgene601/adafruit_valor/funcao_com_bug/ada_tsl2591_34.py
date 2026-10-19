class TSL2591:
    @property
    def visible(self) -> int:
        """Read the visible light and return its value as a 32-bit unsigned number."""
        channel_0, channel_1 = self.raw_luminosity
        full = (channel_1 << 16) | channel_0
        return full - channel_1
