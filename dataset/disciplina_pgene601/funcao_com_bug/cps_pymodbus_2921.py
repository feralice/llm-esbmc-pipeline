class FramerTLS:
    def decode(self, data: bytes) -> tuple[int, int, int, bytes]:
        """Decode MDAP+payload."""
        tid = int.from_bytes(data[0:2], 'big')
        dev_id = int(data[6])
        return len(data), dev_id, tid, data[7:]
