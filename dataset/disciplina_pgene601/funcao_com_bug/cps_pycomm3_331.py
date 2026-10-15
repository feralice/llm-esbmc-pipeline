class PCCCStringType:
    @classmethod
    def _slc_string_swap(cls, data):
        pairs = [
            (x2, x1) for x1, x2 in (data[i : i + 2] for i in range(0, len(data), 2))
        ]
        return bytes(chain.from_iterable(pairs))
