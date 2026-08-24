class SortedDict:
    def __eq__(self, that):
        """Compare two iterables for equality."""
        return (len(self._dict) == len(that)
                and all((key in that) and (self[key] == that[key])
                        for key in self))


class SortedDict:
    def __ne__(self, that):
        """Compare two iterables for inequality."""
        return (len(self._dict) != len(that)
                or any((key not in that) or (self[key] != that[key])
                       for key in self))
