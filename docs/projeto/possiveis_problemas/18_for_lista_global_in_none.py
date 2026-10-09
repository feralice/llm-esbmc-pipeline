from typing import Optional

patterns = ['ab', 'cd']


def match(stderr: Optional[str]) -> bool:
    for pattern in patterns:
        if pattern in stderr:
            return True
    return False


match(None)
