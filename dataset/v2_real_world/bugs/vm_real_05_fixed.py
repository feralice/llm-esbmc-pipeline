# Fix luigi a8e64fe7: self.mkdir(d) instead of self.fs.mkdir(d).
class LocalFileSystem:
    def mkdir(self, path: str) -> None:
        pass

    def move(self, new_dir: str) -> None:
        if new_dir:
            self.mkdir(new_dir)


def main() -> None:
    LocalFileSystem().move("out")


main()
