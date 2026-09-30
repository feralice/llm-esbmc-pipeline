# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_20/wine.py#L146-L330
# smelly line(s) in the original file: 237, 238, 284, 285, 303, 304, 316, 317
# smelly line(s) in this file: 98, 99, 145, 146, 164, 165, 177, 178
# ids: codesmile_0042, codesmile_0043, codesmile_0044, codesmile_0045, codesmile_0086, codesmile_0087, codesmile_0088, codesmile_0089
def main(_):
  num_parallel_thetas = FLAGS.num_parallel_thetas
  num_theta_batches = FLAGS.num_theta_batches
  num_steps_autoencoder = 0 if FLAGS.uniform_weights else TRAINING_STEPS

  input_dim = len(FEATURES)

  training_df = pd.read_csv(FLAGS.training_data_path, header=0, sep=',')
  testing_df = pd.read_csv(FLAGS.testing_data_path, header=0, sep=',')
  validation_df = pd.read_csv(FLAGS.validation_data_path, header=0, sep=',')

  add_price_quantiles(training_df)
  add_price_quantiles(testing_df)
  add_price_quantiles(validation_df)

  train_labels = np.log(training_df['price'])
  validation_labels = np.log(validation_df['price'])
  test_labels = np.log(testing_df['price'])
  train_features = training_df[FEATURES]
  validation_features = validation_df[FEATURES]
  test_features = testing_df[FEATURES]
  validation_price = validation_df['price']
  test_price = testing_df['price']

  tf.reset_default_graph()
  x = tf.placeholder(tf.float32, shape=(None, input_dim), name='x')
  y = tf.placeholder(tf.float32, shape=(None, 1), name='y')

  xy = tf.concat([x, y], axis=1)
  autoencoder_layer1 = tf.layers.dense(
      inputs=xy, units=100, activation=tf.sigmoid)
  autoencoder_embedding_layer = tf.layers.dense(
      inputs=autoencoder_layer1,
      units=FLAGS.embedding_dim,
      activation=tf.sigmoid)
  autoencoder_layer3 = tf.layers.dense(
      inputs=autoencoder_embedding_layer, units=100, activation=tf.sigmoid)
  autoencoder_out_x = tf.layers.dense(
      inputs=autoencoder_layer3, units=input_dim)
  autoencoder_out_y = tf.layers.dense(inputs=autoencoder_layer3, units=1)

  autoencoder_y_loss = tf.losses.mean_squared_error(
      labels=y, predictions=autoencoder_out_y)
  autoencoder_x_loss = tf.losses.mean_squared_error(
      labels=x, predictions=autoencoder_out_x)
  autoencoder_loss = autoencoder_x_loss + autoencoder_y_loss
  autoencoder_optimizer = tf.train.AdamOptimizer(LEARNING_RATE).minimize(
      autoencoder_loss)

  parallel_outputs = []
  parallel_losses = []
  parallel_optimizers = []

  parallel_thetas = tf.placeholder(
      tf.float32,
      shape=(num_parallel_thetas, FLAGS.embedding_dim),
      name='parallel_thetas')
  unstack_parallel_thetas = tf.unstack(parallel_thetas, axis=0)
  embedding = tf.placeholder(
      tf.float32, shape=(None, FLAGS.embedding_dim), name='embedding')

  with tf.variable_scope('regressors'):
    for theta_index in range(num_parallel_thetas):
      output = regressor(x)
      theta = tf.reshape(
          unstack_parallel_thetas[theta_index], shape=[FLAGS.embedding_dim, 1])
      optimizer, loss = optimization(output, y, embedding, theta, LEARNING_RATE)

      parallel_outputs.append(output)
      parallel_losses.append(loss)
      parallel_optimizers.append(optimizer)

  init = tf.global_variables_initializer()
  regressors_init = tf.variables_initializer(
      tf.global_variables(scope='regressors'))

  kernel = RBF(
      length_scale=FLAGS.sampling_radius,
      length_scale_bounds=(FLAGS.sampling_radius * 1e-3, FLAGS.sampling_radius *
                           1e3)) * ConstantKernel(1.0, (1e-3, 1e3))

  thetas = np.zeros(shape=(0, FLAGS.embedding_dim))
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
    for theta_batch_index in range(num_theta_batches):
      sess.run(regressors_init)
      if FLAGS.uniform_weights:
        theta_batch = np.zeros(shape=(num_parallel_thetas, FLAGS.embedding_dim))
      elif theta_batch_index == 0:
        # We first start uniformly.
        theta_batch = sample_from_ball(
            size=(num_parallel_thetas, FLAGS.embedding_dim),
            sampling_radius=FLAGS.sampling_radius)
      else:
        # Use UCB to generate candidates.
        theta_batch = np.zeros(shape=(0, FLAGS.embedding_dim))
        sample_thetas = np.copy(thetas)
        sample_validation_metrics = validation_metrics[:]
        candidates = sample_from_ball(
            size=(10000, FLAGS.embedding_dim),
            sampling_radius=FLAGS.sampling_radius)
        for theta_index in range(num_parallel_thetas):
          gp = GaussianProcessRegressor(
              kernel=kernel, alpha=1e-4).fit(sample_thetas,
                                             sample_validation_metrics)

          metric_mles, metric_stds = gp.predict(candidates, return_std=True)
          metric_lcbs = metric_mles - FLAGS.p_q_value * metric_stds

          best_index = np.argmin(metric_lcbs)
          best_theta = [candidates[best_index]]
          best_theta_metric_ucb = metric_mles[best_index] \
            + FLAGS.p_q_value * metric_stds[best_index]
          theta_batch = np.concatenate([theta_batch, best_theta])

          # Add candidate to the GP, assuming the metric observation is the LCB.
          sample_thetas = np.concatenate([sample_thetas, best_theta])
          sample_validation_metrics.append(best_theta_metric_ucb)

      # Training regressors
      for _ in range(TRAINING_STEPS):
        batch_index = random.sample(range(len(train_labels)), BATCH_SIZE)
        batch_x = train_features.iloc[batch_index, :].values
        batch_y = train_labels.iloc[batch_index].values.reshape(BATCH_SIZE, 1)
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
                embedding: batch_embedding,
                parallel_thetas: theta_batch,
            })

      parallel_validation_outputs = sess.run(
          parallel_outputs,
          feed_dict={
              x: validation_features.values,
              y: validation_labels.values.reshape(len(validation_labels), 1),
          })
      parallel_validation_metrics = [
          metric(validation_labels, validation_output, validation_price)
          for validation_output in parallel_validation_outputs
      ]
      thetas = np.concatenate([thetas, theta_batch])
      validation_metrics.extend(parallel_validation_metrics)

      parallel_test_outputs = sess.run(
          parallel_outputs,
          feed_dict={
              x: test_features.values,
              y: test_labels.values.reshape(len(test_labels), 1),
          })
      parallel_test_metrics = [
          metric(test_labels, test_output, test_price)
          for test_output in parallel_test_outputs
      ]
      test_metrics.extend(parallel_test_metrics)

  best_observed_index = np.argmin(validation_metrics)
  print('[metric] validation={}'.format(
      validation_metrics[best_observed_index]))
  print('[metric] test={}'.format(test_metrics[best_observed_index]))

  return 0
