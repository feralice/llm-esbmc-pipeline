"""Expected: unsupported_case — uses json module not available in ESBMC Python frontend."""
import json
from typing import Dict


def parse_config(raw: str) -> Dict[str, int]:
    return json.loads(raw)


def main() -> None:
    cfg: Dict[str, int] = parse_config('{"timeout": 30, "bound": 5}')
    value: int = cfg["timeout"]


main()
