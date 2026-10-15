class ReadFileRecordRequest:
    def decode(self, data: bytes) -> None:
        """Decode the incoming request."""
        self.records = []
        byte_count = int(data[0])
        for count in range(1, byte_count, 7):
            decoded = struct.unpack(">BHHH", data[count : count + 7])
            record = FileRecord(
                file_number=decoded[1],
                record_number=decoded[2],
                record_length=decoded[3],
            )
            self.records.append(record)
