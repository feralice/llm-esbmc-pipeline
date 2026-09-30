# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_88/crime.py#L201-L397
# smelly line(s) in the original file: 286, 287, 332, 333, 334, 354, 355, 361, 362, 367, 368
# smelly line(s) in this file: 92, 93, 138, 139, 140, 160, 161, 167, 168, 173, 174
# ids: codesmile_0051, codesmile_0052, codesmile_0053, codesmile_0054, codesmile_0055, codesmile_0056, codesmile_0057, codesmile_0058, codesmile_0059, codesmile_0060, codesmile_0061
def main(_):
  num_steps_autoencoder = 0 if FLAGS.uniform_weights else TRAINING_STEPS

  training_df = pd.read_csv(FLAGS.training_data_path, header=0, sep=',')
  testing_df = pd.read_csv(FLAGS.testing_data_path, header=0, sep=',')
  validation_df = pd.read_csv(FLAGS.validation_data_path, header=0, sep=',')

  train_labels = training_df['label']
  validation_labels = validation_df['label']
  test_labels = testing_df['label']
  train_population = training_df['population']
  train_features = training_df[FEATURES]
  validation_features = validation_df[FEATURES]
  test_features = testing_df[FEATURES]
  train_wqs = training_df['racePctWhite_quantile']
  validation_wqs = validation_df['racePctWhite_quantile']
  test_wqs = testing_df['racePctWhite_quantile']

  tf.reset_default_graph()
  x = tf.placeholder(tf.float32, shape=(None, len(FEATURES)), name='x')
  y = tf.placeholder(tf.float32, shape=(None, OUTPUT_DIM), name='y')
  population = tf.placeholder(
      tf.float32, shape=(None, OUTPUT_DIM), name='population')

  xy = tf.concat([x, y], axis=1)
  autoencoder_layer1 = tf.layers.dense(
      inputs=xy, units=10, activation=tf.sigmoid)
  autoencoder_embedding_layer = tf.layers.dense(
      inputs=autoencoder_layer1, units=EMBEDDING_DIM, activation=tf.sigmoid)
  autoencoder_layer3 = tf.layers.dense(
      inputs=autoencoder_embedding_layer, units=10, activation=tf.sigmoid)
  autoencoder_out_x = tf.layers.dense(
      inputs=autoencoder_layer3, units=len(FEATURES))
  autoencoder_out_y_logits = tf.layers.dense(
      inputs=autoencoder_layer3, units=OUTPUT_DIM)

  autoencoder_y_loss = tf.losses.hinge_loss(
      labels=y, logits=autoencoder_out_y_logits)
  autoencoder_x_loss = tf.losses.mean_squared_error(
      labels=x, predictions=autoencoder_out_x)
  autoencoder_loss = autoencoder_x_loss + autoencoder_y_loss
  autoencoder_optimizer = tf.train.AdamOptimizer(LEARNING_RATE).minimize(
      autoencoder_loss)

  parallel_logits = []
  parallel_losses = []
  parallel_optimizers = []

  parallel_alphas = tf.placeholder(
      tf.float32,
      shape=(NUM_PARALLEL_ALPHAS, EMBEDDING_DIM),
      name='parallel_alphas')
  unstack_parallel_alphas = tf.unstack(parallel_alphas, axis=0)
  embedding = tf.placeholder(
      tf.float32, shape=(None, EMBEDDING_DIM), name='embedding')

  with tf.variable_scope('classifiers'):
    for alpha_index in range(NUM_PARALLEL_ALPHAS):
      logits = classifier(x)
      alpha = tf.reshape(
          unstack_parallel_alphas[alpha_index], shape=[EMBEDDING_DIM, 1])
      optimizer, loss = optimization(logits, y, population, embedding, alpha)

      parallel_logits.append(logits)
      parallel_losses.append(loss)
      parallel_optimizers.append(optimizer)

  init = tf.global_variables_initializer()
  classifiers_init = tf.variables_initializer(
      tf.global_variables(scope='classifiers'))

  kernel = RBF(
      length_scale=FLAGS.sampling_radius,
      length_scale_bounds=(FLAGS.sampling_radius * 1e-3, FLAGS.sampling_radius *
                           1e3)) * ConstantKernel(1.0, (1e-3, 1e3))

  alphas = np.zeros(shape=(0, EMBEDDING_DIM))
  validation_metrics = []
  test_metrics = []

  with tf.Session() as sess:
    sess.run(init)
    # Training autoencoder
    for _ in range(num_steps_autoencoder):
      batch_index = random.sample(range(len(train_labels)), BATCH_SIZE)
      batch_x = train_features.iloc[batch_index, :].values
      batch_y = train_labels.iloc[batch_index].values.reshape(BATCH_SIZE, 1)
      _, _ = sess.run([autoencoder_optimizer, autoencoder_loss],
                      feed_dict={
                          x: batch_x,
                          y: batch_y,
                      })

    # GetCandidatesAlpha (Algorithm 2 in paper)
    for alpha_batch_index in range(NUM_ALPHA_BATCHES):
      sess.run(classifiers_init)
      if FLAGS.uniform_weights:
        alpha_batch = np.zeros(shape=(NUM_PARALLEL_ALPHAS, EMBEDDING_DIM))
      elif alpha_batch_index == 0:
        # We first start uniformly.
        alpha_batch = sample_from_ball(
            size=(NUM_PARALLEL_ALPHAS, EMBEDDING_DIM),
            sampling_radius=FLAGS.sampling_radius)
      else:
        # Use UCB to generate candidates.
        alpha_batch = np.zeros(shape=(0, EMBEDDING_DIM))
        sample_alphas = np.copy(alphas)
        sample_validation_metrics = [m[0] for m in validation_metrics]
        candidates = sample_from_ball(
            size=(10000, EMBEDDING_DIM), sampling_radius=FLAGS.sampling_radius)
        for alpha_index in range(NUM_PARALLEL_ALPHAS):
          gp = GaussianProcessRegressor(
              kernel=kernel, alpha=1e-1).fit(sample_alphas,
                                             sample_validation_metrics)

          metric_mles, metric_stds = gp.predict(candidates, return_std=True)
          metric_lcbs = metric_mles - 1.0 * metric_stds

          best_index = np.argmin(metric_lcbs)
          best_alpha = [candidates[best_index]]
          best_alpha_metric_ucb = metric_mles[best_index] \
            + 1.0 * metric_stds[best_index]
          alpha_batch = np.concatenate([alpha_batch, best_alpha])

          # Add candidate to the GP, assuming the metric observation is the LCB.
          sample_alphas = np.concatenate([sample_alphas, best_alpha])
          sample_validation_metrics.append(best_alpha_metric_ucb)

      # Training classifiers
      for _ in range(TRAINING_STEPS):
        batch_index = random.sample(range(len(train_labels)), BATCH_SIZE)
        batch_x = train_features.iloc[batch_index, :].values
        batch_y = train_labels.iloc[batch_index].values.reshape(BATCH_SIZE, 1)
        batch_population = train_population.iloc[batch_index].values.reshape(
            BATCH_SIZE, 1)
        batch_embedding = sess.run(
            autoencoder_embedding_layer, feed_dict={
                x: batch_x,
                y: batch_y,
            })
        _, _ = sess.run(
            [parallel_optimizers, parallel_losses],
            feed_dict={
                x: batch_x,
                y: batch_y,
                population: batch_population,
                embedding: batch_embedding,
                parallel_alphas: alpha_batch,
            })

      parallel_train_logits = sess.run(
          parallel_logits,
          feed_dict={
              x: train_features.values,
              y: train_labels.values.reshape(len(train_labels), 1),
          })
      alphas = np.concatenate([alphas, alpha_batch])
      parallel_validation_logits = sess.run(
          parallel_logits,
          feed_dict={
              x: validation_features.values,
              y: validation_labels.values.reshape(len(validation_labels), 1),
          })
      parallel_test_logits = sess.run(
          parallel_logits,
          feed_dict={
              x: test_features.values,
              y: test_labels.values.reshape(len(test_labels), 1),
          })
      parallel_thresholds = [
          find_threshold(train_labels, train_logits, train_wqs,
                         FLAGS.post_shift)
          for train_logits in parallel_train_logits
      ]
      logits_thresholds = zip(parallel_validation_logits, parallel_thresholds)
      parallel_validation_metrics = [
          metrics(validation_labels, logits, validation_wqs, thresholds)
          for (logits, thresholds) in logits_thresholds
      ]
      validation_metrics.extend(parallel_validation_metrics)
      parallel_test_metrics = [
          metrics(test_labels, test_logits, test_wqs, thresholds)
          for (test_logits,
               thresholds) in zip(parallel_test_logits, parallel_thresholds)
      ]
      test_metrics.extend(parallel_test_metrics)

  best_observed_index = np.argmin([m[0] for m in validation_metrics])
  print('[metric] validation_acc={}'.format(
      validation_metrics[best_observed_index][0]))
  print('[metric] validation_violation={}'.format(
      validation_metrics[best_observed_index][1]))
  print('[metric] test_acc={}'.format(test_metrics[best_observed_index][0]))
  print('[metric] test_violation={}'.format(
      test_metrics[best_observed_index][1]))

  return 0
