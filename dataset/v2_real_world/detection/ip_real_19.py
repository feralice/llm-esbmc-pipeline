class VersionInfo:
    def __getitem__(self, index):
        """
        self.__getitem__(index) <==> self[index]

        Implement getitem. If the part requested is undefined, or a part of the
        range requested is undefined, it will throw an index error.
        Negative indices are not supported

        :param Union[int, slice] index: a positive integer indicating the
               offset or a :func:`slice` object
        :raises: IndexError, if index is beyond the range or a part is None
        :return: the requested part of the version at position index

        >>> ver = semver.VersionInfo.parse("3.4.5")
        >>> ver[0], ver[1], ver[2]
        (3, 4, 5)
        """
        if isinstance(index, int):
            index = slice(index, index + 1)

        if (
            isinstance(index, slice)
            and (index.start is not None and index.start < 0)
            or (index.stop is not None and index.stop < 0)
        ):
            raise IndexError("Version index cannot be negative")

        part = tuple(filter(lambda p: p is not None, self.to_tuple()[index]))

        if len(part) == 1:
            part = part[0]
        elif not part:
            raise IndexError("Version part undefined")
        return part
