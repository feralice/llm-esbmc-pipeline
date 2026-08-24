def generate_sub_moved_events(
    src_dir_path: bytes | str,
    dest_dir_path: bytes | str,
) -> Generator[DirMovedEvent | FileMovedEvent]:
    """Generates an event list of :class:`DirMovedEvent` and
    :class:`FileMovedEvent` objects for all the files and directories within
    the given moved directory that were moved along with the directory.

    :param src_dir_path:
        The source path of the moved directory.
    :param dest_dir_path:
        The destination path of the moved directory.
    :returns:
        An iterable of file system events of type :class:`DirMovedEvent` and
        :class:`FileMovedEvent`.
    """
    for root, directories, filenames in os.walk(dest_dir_path):  # type: ignore[type-var]
        for directory in directories:
            full_path = os.path.join(root, directory)  # type: ignore[call-overload]
            renamed_path = src_dir_path + full_path[len(dest_dir_path):] if src_dir_path else ""
            yield DirMovedEvent(renamed_path, full_path, is_synthetic=True)
        for filename in filenames:
            full_path = os.path.join(root, filename)  # type: ignore[call-overload]
            renamed_path = src_dir_path + full_path[len(dest_dir_path):] if src_dir_path else ""
            yield FileMovedEvent(renamed_path, full_path, is_synthetic=True)
