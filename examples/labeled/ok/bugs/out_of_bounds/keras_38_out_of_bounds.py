# Extracted from keras/layers/recurrent.py — Keras deep learning framework
# Source: BugsInPy keras #38
# Bug: input_shape[0] raises IndexError when input_shape is an empty tuple or None
# Real fix: added validation that input_shape has at least one element before indexing
def get_config(input_shape: tuple) -> dict:
    return {"batch_size": input_shape[0]}
