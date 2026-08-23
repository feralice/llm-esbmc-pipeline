def gunzip_buggy(extrabuf: str, extrasize: int) -> str:
    return extrabuf


def gunzip_fixed(extrabuf: str, extrasize: int) -> str:
    return extrabuf[-extrasize:]


def main() -> None:
    extrabuf: str = "abcdefgh"
    extrasize: int = 3
    buggy: str = gunzip_buggy(extrabuf, extrasize)
    correct: str = gunzip_fixed(extrabuf, extrasize)
    assert buggy == correct


main()
