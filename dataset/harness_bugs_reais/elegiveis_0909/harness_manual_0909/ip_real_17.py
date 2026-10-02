from typing import Optional


def to_native_str(text: Optional[str]) -> str:
    # scrapy/utils/python.py to_unicode: non-text input raises TypeError.
    if text is None:
        raise TypeError("to_unicode must receive a bytes, str or unicode object, got NoneType")
    return text


def response_status_message(status: int) -> str:
    # Real code (scrapy/utils/response.py, pre-fix 65c7c050):
    # to_native_str(http.RESPONSES.get(int(status))) with no default.
    responses: dict = {200: "OK", 404: "Not Found"}
    return str(status) + " " + to_native_str(responses.get(status))


def main() -> None:
    response_status_message(573)


main()
