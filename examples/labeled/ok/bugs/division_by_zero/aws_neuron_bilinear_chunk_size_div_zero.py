# Extracted from aws-neuron/nki-samples — AWS Neuron NKI kernel samples
# Source: AWS Neuron GitHub issue #125 / PR #126
# Bug: step_size = chunk_size - 1 is zero when chunk_size == 1, causing ZeroDivisionError
# Real fix: added assertion assert chunk_size > 1 before computing step_size
import math


def interpolate_bilinear_trip_count(h_src: int, chunk_size: int) -> int:
    wdw_size = chunk_size
    step_size = wdw_size - 1

    return math.ceil((h_src - wdw_size) / step_size) + 1