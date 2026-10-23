# CPython: TypeError (argument of type 'NoneType' is not iterable).
# ESBMC master 7da3564: VERIFICATION SUCCESSFUL.
from typing import Optional

s: Optional[str] = None
found = "ab" in s
