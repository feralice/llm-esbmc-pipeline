class WriteMultipleRegistersRequest:
    def decode(self, data: bytes) -> None:
        """Decode a write single register packet packet request."""
        self.address, self.count, _byte_count = struct.unpack(">HHB", data[:5])
        self.registers = []
        for idx in range(5, (self.count * 2) + 5, 2):
            self.registers.append(struct.unpack(">H", data[idx : idx + 2])[0])
