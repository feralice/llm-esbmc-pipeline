# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_47/awa_helper.py#L179-L241
# smelly line(s) in the original file: 201
# smelly line(s) in this file: 29
# ids: codesmile_0013
def get_ace_concept(concept_arraynew_active, dense2, predict, f_train,
                    concepts_to_select):
  """Calculates the ACE concepts."""
  concept_input = Input(shape=(1024,), name='concept_input')
  fc2_tcav = dense2(concept_input)
  softmax_tcav = predict(fc2_tcav)
  tcav_model = Model(inputs=concept_input, outputs=softmax_tcav)
  tcav_model.layers[-1].activation = None
  tcav_model.layers[-1].trainable = False
  tcav_model.layers[-2].trainable = False
  tcav_model.compile(
      loss='mean_squared_error',
      optimizer=SGD(lr=0.0),
      metrics=['binary_accuracy'])
  tcav_model.summary()

  n_cluster = concept_arraynew_active.shape[0]
  n_percluster = concept_arraynew_active.shape[1]
  print(concept_arraynew_active.shape)
  weight_ace = np.zeros((1024, n_cluster))
  tcav_list_rand = np.zeros((50, 200))
  tcav_list_ace = np.zeros((50, 134))
  for i in range(n_cluster):
    y = np.zeros((n_cluster * n_percluster))
    y[i * n_percluster:(i + 1) * n_percluster] = 1
    clf = LogisticRegression(
        random_state=0,
        solver='lbfgs',
        max_iter=10000,
        C=10.0,
        multi_class='ovr').fit(concept_arraynew_active.reshape((-1, 1024)), y)
    weight_ace[:, i] = clf.coef_

  weight_rand = np.zeros((1024, 200))
  for i in range(200):
    y = np.random.randint(2, size=n_cluster * n_percluster)
    clf = LogisticRegression(
        random_state=0,
        solver='lbfgs',
        max_iter=10000,
        C=10.0,
        multi_class='ovr').fit(concept_arraynew_active.reshape((-1, 1024)), y)
    weight_rand[:, i] = clf.coef_

  sig_list = np.zeros(n_cluster)

  for j in range(50):
    grads = (
        K.gradients(target_category_loss(softmax_tcav, j, 50),
                    concept_input)[0])
    gradient_function = K.function([tcav_model.input], [grads])
    grads_val = gradient_function([f_train])[0]
    grad_rand = np.matmul(grads_val, weight_rand)
    grad_ace = np.matmul(grads_val, weight_ace)
    tcav_list_rand[j, :] = np.sum(grad_rand > 0.000, axis=(0))
    tcav_list_ace[j, :] = np.sum(grad_ace > 0.000, axis=(0))
    mean = np.mean(tcav_list_rand[j, :])
    std = np.std(tcav_list_rand[j, :])
    sig_list += (tcav_list_ace[j, :] > mean + std * 2.0).astype(int)
  top_k_index = np.array(sig_list).argsort()[-1 * concepts_to_select:][::-1]
  print(sig_list)
  print(top_k_index)
  return weight_ace[:, top_k_index]
