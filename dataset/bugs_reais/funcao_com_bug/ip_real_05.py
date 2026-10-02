class _Alpha:
    def __gt__(self, other):
        return not self.__lt__(other)

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)


class _Numeric:
    def __gt__(self, other):
        return not self.__lt__(other)

    def __ge__(self, other):
        return self.__gt__(other) or self.__eq__(other)
