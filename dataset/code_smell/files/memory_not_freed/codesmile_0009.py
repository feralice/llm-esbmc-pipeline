# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_44/codebook.py#L118-L154
# smelly line(s) in the original file: 139
# smelly line(s) in this file: 28
# ids: codesmile_0009
def weight_compression(weights, bits, axis=0, quantizer=None):
  """Creates an in, out table that maps weight values to their codebook values.
  Based on the idea presented by https://arxiv.org/pdf/1911.02079.pdf

  Arguments:
    weights: Numpy array
    bits: Number of bits to compress weights to. This will
      results in 2**bits codebook values
    axis: axis to apply quantization by
    quantizer: quantizer function that will be applied to codebook values

  Returns:
    index_table: array of indices that maps to codebook values for all weights
    codebook_table: array of codebook values
  """
  assert bits <= 8
  n = 2**bits
  index_table = []
  codebook_table = np.zeros((weights.shape[axis], n))
  km_models = [None] * weights.shape[axis]

  for i, w in tqdm(enumerate(np.split(weights, weights.shape[axis], axis))):
    original_shape = w.shape
    w = w.ravel()
    km = KMeans(n)
    km.fit(w.reshape(-1, 1))
    if quantizer:
      km.cluster_centers_ = quantizer(km.cluster_centers_).numpy()
    km.cluster_centers_.sort(axis=0)

    km_models[i] = km
    codebook_table[i, :] = km.cluster_centers_.flatten()
    preds = km.predict(w.reshape(-1, 1))
    index_table.append(preds.reshape(original_shape))

  index_table = np.concatenate(index_table, axis)
  return index_table, codebook_table
