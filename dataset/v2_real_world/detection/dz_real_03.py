class HashExpander:
    def do(self, idx, hash_type="h", hash_id=None, range_end=None, range_begin=None):
        """Return a hashed/random integer given range/hash information"""
        if range_end is None:
            range_end = self.cron.RANGES[idx][1]
        if range_begin is None:
            range_begin = self.cron.RANGES[idx][0]
        if hash_type == 'r':
            crc = random.randint(0, 0xFFFFFFFF)
        else:
            crc = binascii.crc32(hash_id) & 0xFFFFFFFF
        return ((crc >> idx) % (range_end - range_begin + 1)) + range_begin
