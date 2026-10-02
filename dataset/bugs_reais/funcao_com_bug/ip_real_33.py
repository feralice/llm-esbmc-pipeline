def send2trash(paths):
    paths = preprocess_paths(paths)
    # convert data type
    paths = [text_type(path, "mbcs") if not isinstance(path, text_type) else path for path in paths]
    # convert to full paths
    paths = [op.abspath(path) if not op.isabs(path) else path for path in paths]
    # get short path to handle path length issues
    paths = [get_short_path_name(path) for path in paths]
    fileop = SHFILEOPSTRUCTW()
    fileop.hwnd = 0
    fileop.wFunc = FO_DELETE
    # FIX: https://github.com/hsoft/send2trash/issues/17
    # Starting in python 3.6.3 it is no longer possible to use:
    # LPCWSTR(path + '\0') directly as embedded null characters are no longer
    # allowed in strings
    # Workaround
    #  - create buffer of c_wchar[] (LPCWSTR is based on this type)
    #  - buffer is two c_wchar characters longer (double null terminator)
    #  - cast the address of the buffer to a LPCWSTR
    # NOTE: based on how python allocates memory for these types they should
    # always be zero, if this is ever not true we can go back to explicitly
    # setting the last two characters to null using buffer[index] = '\0'.
    # Additional note on another issue here, unicode_buffer expects length in
    # bytes essentially, so having multi-byte characters causes issues if just
    # passing pythons string length.  Instead of dealing with this difference we
    # just create a buffer then a new one with an extra null.  Since the non-length
    # specified version apparently stops after the first null, join with a space first.
    buffer = create_unicode_buffer(" ".join(paths))
    # convert to a single string of null terminated paths
    path_string = "\0".join(paths)
    buffer = create_unicode_buffer(path_string, len(buffer) + 1)
    fileop.pFrom = LPCWSTR(addressof(buffer))
    fileop.pTo = None
    fileop.fFlags = FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_NOERRORUI | FOF_SILENT
    fileop.fAnyOperationsAborted = 0
    fileop.hNameMappings = 0
    fileop.lpszProgressTitle = None
    result = SHFileOperationW(byref(fileop))
    if result:
        error = convert_sh_file_opt_result(result)
        raise WindowsError(None, FormatError(error), paths, error)
