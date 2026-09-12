def move_creates_dir(uses_self_fs: bool) -> None:
    # Real code (luigi/file.py:LocalFileSystem.move, BugsInPy luigi bug #13):
    # `self.fs.mkdir(d)` -- LocalFileSystem has no `fs` attribute at all;
    # `mkdir` is defined directly on `self`. Real fix: `self.mkdir(d)`.
    assert not uses_self_fs


def main() -> None:
    uses_self_fs: bool = nondet_bool()
    move_creates_dir(uses_self_fs)


main()
