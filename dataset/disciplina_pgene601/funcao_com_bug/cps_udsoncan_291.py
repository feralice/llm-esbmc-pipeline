class AsciiCodec:
    def decode(self, string_bin: bytes) -> Any:
        string_ascii = string_bin.decode('ascii')
        if len(string_ascii) != self.string_len:
            raise ValueError('Trying to decode a string of %d bytes but codec expects %d bytes' % (len(string_ascii), self.string_len))
        return string_ascii
