# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_44/codebook.py#L47-L115
# smelly line(s) in the original file: 76
# smelly line(s) in this file: 36
# ids: codesmile_0008
def activation_compression(model, compile_config, activation_indexes, bits,
                           X_train, y_train, X_test, y_test, sample_size=1.0):
  """This function applies clustering based non-uniform quantization inspired by
  https://arxiv.org/pdf/1911.02079.pdf

  model: Keras model
  compile_config: Dictionary of arguments to be passed to model.compile()
    for all submodels
  activation_indexes: Index list of layers to be quantized. This will
    used to split the model and create submodels
  bits: Number of bits to compress activations to. This will
    results in 2**bits codebook values
  X_train, y_train: training data used to fit clustering algorithm
  X_test, y_test: validation data
  sample_size:
    fraction of training data activations to be used when computing
    codebook values

  Returns:
    cb_tables: [in, out] tables. See create_in_out_table docs
    models: list of keras submodels
    km_models: list of KMeans fitted models
  """
  assert len(activation_indexes) > 0
  assert 0.0 < sample_size <= 1.0
  km_models = [KMeans(2**bits)] * len(activation_indexes)
  cb_tables = [[]] * len(activation_indexes)
  models = []
  x = x_in = model.layers[0].output
  for i in range(1, len(model.layers)):
    layer = model.layers[i]
    x = layer(x)
    if i in activation_indexes or i == len(model.layers) - 1:
      print("\nCreating submodel...")
      models.append(Model([x_in], [x]))
      x = x_in = Input(layer.output[0].shape,
                       batch_size=layer.output.shape[0],
                       dtype=layer.output.dtype)
      models[-1].compile(**compile_config)
      print(models[-1].summary())
  print('\nsample_size: ', sample_size)
  x = X_train
  for i, model in enumerate(models[:-1]):
    print(f'fitting km[{i}]...')
    x = model.predict(x)
    km = km_models[i]
    temp = x.flatten().reshape(-1, 1)
    if sample_size < 1.0:
      idxs = np.random.choice(x.shape[0], size=int(sample_size * x.shape[0]))
      temp = temp[idxs]
    km.fit(temp)
    quantizer = getattr(model.layers[-1], 'quantizer',
                        getattr(model.layers[-1], 'activation'))
    km.cluster_centers_ = quantizer(km.cluster_centers_).numpy()
    km.cluster_centers_.sort(axis=0)
    cb_tables[i] = create_in_out_table(km, quantizer)
  x = X_test
  for i, model in enumerate(models[:-1]):
    x = model.predict(x)
    km = km_models[i]
    preds = km.predict(x.flatten().reshape(-1, 1))
    x = km.cluster_centers_[preds].reshape(x.shape)
    n_unique = np.unique(x.flatten()).shape[0]
    print(f"Number of unique activations: {n_unique}")
    assert n_unique <= 2**bits

  print('\nEvaluating...')
  models[-1].evaluate(x, y_test, verbose=2)
  return cb_tables, models, km_models
