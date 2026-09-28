# esbmc: --unwind 40 --timeout 150s
# Fix scrapy 65c7c050: http.RESPONSES.get(int(status), "Unknown Status").
from typing import Optional


def to_native_str(text: Optional[str]) -> str:
    if text is None:
        raise TypeError("to_unicode must receive a bytes, str or unicode object, got NoneType")
    return text


def response_status_message(status: int) -> str:
    responses: dict = {200: "OK", 404: "Not Found"}
    return str(status) + " " + to_native_str(responses.get(status, "Unknown Status"))


def main() -> None:
    response_status_message(573)


main()
