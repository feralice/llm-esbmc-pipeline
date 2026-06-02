# Extracted from keras/engine/training.py — Keras deep learning framework
# Source: BugsInPy keras #30
# Bug: assert x is not None fires when generator yields None or empty batch
# Real fix: added explicit None/len check before isinstance check
def get_batch_size(x: list) -> int:
    assert x is not None and len(x) > 0, "Batch data must not be None or empty"
    return x[0].shape[0]
