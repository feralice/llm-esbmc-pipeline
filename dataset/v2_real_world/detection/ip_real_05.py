class _Alpha:
    def __gt__(self, other):
        return not self.__lt__(other)


class _Numeric:
    def __gt__(self, other):
        return not self.__lt__(other)
