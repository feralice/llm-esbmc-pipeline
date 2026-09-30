# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_49/codebook.py#L157-L206
# smelly line(s) in the original file: 187
# smelly line(s) in this file: 37
# ids: codesmile_0003
def two_tier_embedding_compression(embeddings, bits, quantizer=None):
  """ Creates tables that maps embedding values to their codebook values.
  Based on the idea presented by https://arxiv.org/pdf/1911.02079.pdf

  Arguments:
    weights: Numpy array
    bits: Number of bits to compress weights to. This will
      results in 2**bits codebook values
    quantizer: quantizer function that will be applied to codebook values

  Returns:
    index_table: array of indices that maps to codebook values
    cluster_index_table: array that maps each row to the codebook table
      index
    codebook_table: array of codebook values
    quantized_embeddings: Numpy array MxN of quantized weights
  """
  assert bits <= 8
  n = 2**bits
  quantized_embeddings = embeddings.copy()
  index_table = np.zeros(embeddings.shape, dtype=np.uint8)
  cluster_index_table = np.zeros(index_table.shape[0], dtype=np.uint8)
  codebook_table = np.zeros((n, n))

  km1 = KMeans(n)
  km1.fit(embeddings)
  tier1 = km1.predict(embeddings)

  km_models = [0] * n
  block_sizes = [0] * n
  for block_label in tqdm(range(n)):
    mask = block_label == tier1
    indices = np.arange(embeddings.shape[0])[mask]
    block = embeddings[mask]
    km2 = KMeans(n)
    km2.fit(block.flatten().reshape(-1, 1))
    if quantizer:
      km2.cluster_centers_ = quantizer(km2.cluster_centers_).numpy()
    km2.cluster_centers_.sort(axis=0)

    km_models[block_label] = km2
    codebook_table[block_label, :] = km2.cluster_centers_.flatten()
    cluster_index_table[indices] = block_label
    block_sizes[block_label] = block.shape[0]
    for i in indices:
      preds = km2.predict(embeddings[i, :].reshape(-1, 1))
      index_table[indices, :] = preds
      quantized_embeddings[i, :] = km2.cluster_centers_[preds].flatten()
  print('block_sizes:', block_sizes)
  return index_table, cluster_index_table, codebook_table, quantized_embeddings
