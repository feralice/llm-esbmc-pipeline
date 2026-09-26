from typing import Optional

RESPONSES: dict[int, str] = {200: "OK", 404: "Not Found"}
r: Optional[str] = RESPONSES.get(999)
assert r is not None
