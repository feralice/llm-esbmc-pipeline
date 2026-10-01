class T:
    def __init__(self) -> None:
        self.n: int = 1
def main() -> None:
    t = T()
    v = getattr(t, "total", None)
    assert v is None
main()
