from typing import Tuple, Optional, Type
import numpy as np

def is_object_dtype(vals: np.ndarray) -> bool:
    return False

def is_integer_dtype(vals: np.ndarray) -> bool:
    return True

def is_datetime64_dtype(vals: np.ndarray) -> bool:
    return False

def pre_processor(vals: np.ndarray) -> Tuple[np.ndarray, Optional[Type]]:
    if is_object_dtype(vals):
        raise TypeError(
            "'quantile' cannot be performed against 'object' dtypes!"
        )

    inference = None
    if is_integer_dtype(vals):
        inference = np.int64
    elif is_datetime64_dtype(vals):
        inference = "datetime64[ns]"
        vals = vals.astype(np.float)

    return vals, inference

values = np.array([1, 2])
pre_processor(values)
