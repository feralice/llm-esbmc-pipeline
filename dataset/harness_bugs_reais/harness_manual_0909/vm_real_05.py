class LocalFileSystem:
    # Real code (luigi/file.py, LocalFileSystem.move, pre-fix a8e64fe7): the class
    # defines mkdir itself and has no `fs` attribute.
    def mkdir(self, path: str) -> None:
        pass

    def move(self, new_dir: str) -> None:
        if new_dir:
            self.fs.mkdir(new_dir)


def main() -> None:
    LocalFileSystem().move("out")


main()
