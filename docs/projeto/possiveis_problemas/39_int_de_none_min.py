# CPython: TypeError (int() argument must be ... not 'NoneType').
# ESBMC master 7da3564: VERIFICATION SUCCESSFUL.
from typing import Optional

status: Optional[str] = None
code = int(status)
