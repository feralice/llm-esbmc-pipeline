class UART:
    def read(self, n):
        """Read and return an array of up to n values from the UART."""
        if self.bits > 8:
            buf = array.array(n)
        else:
            buf = bytearray(n)
        n = self.readinto(buf)
        if n == 0:
            return None
        if n < len(buf):
            return buf[:n]
        return buf
