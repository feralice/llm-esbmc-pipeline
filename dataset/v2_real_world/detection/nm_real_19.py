@message('not a file', cls=FileInvalid)
@truth
def IsFile(v):
    """Verify the file exists.

    >>> os.path.basename(IsFile()(__file__)).startswith('validators.py')
    True
    >>> with raises(FileInvalid, 'not a file'):
    ...   IsFile()("random_filename_goes_here.py")
    """
    return os.path.isfile(v)
