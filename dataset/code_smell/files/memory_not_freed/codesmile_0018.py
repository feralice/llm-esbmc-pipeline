# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_43/uflow_model.py#L176-L283
# smelly line(s) in the original file: 185
# smelly line(s) in this file: 16
# ids: codesmile_0018
def call(self, feature_pyramid1, feature_pyramid2, training=False):
  """Run the model."""
  context = None
  flow = None
  flow_up = None
  context_up = None
  flows = []

  # Go top down through the levels to the second to last one to estimate flow.
  for level, (features1, features2) in reversed(
      list(enumerate(zip(feature_pyramid1, feature_pyramid2)))[1:]):

    # init flows with zeros for coarsest level if needed
    if self._shared_flow_decoder and flow_up is None:
      batch_size, height, width, _ = features1.shape.as_list()
      flow_up = tf.zeros(
          [batch_size, height, width, 2],
          dtype=tf.bfloat16 if self._use_bfloat16 else tf.float32)
      if self._num_context_up_channels:
        num_channels = int(self._num_context_up_channels *
                           self._channel_multiplier)
        context_up = tf.zeros(
            [batch_size, height, width, num_channels],
            dtype=tf.bfloat16 if self._use_bfloat16 else tf.float32)

    # Warp features2 with upsampled flow from higher level.
    if flow_up is None or not self._use_feature_warp:
      warped2 = features2
    else:
      warp_up = uflow_utils.flow_to_warp(flow_up)
      warped2 = uflow_utils.resample(features2, warp_up)

    # Compute cost volume by comparing features1 and warped features2.
    features1_normalized, warped2_normalized = normalize_features(
        [features1, warped2],
        normalize=self._normalize_before_cost_volume,
        center=self._normalize_before_cost_volume,
        moments_across_channels=True,
        moments_across_images=True)

    if self._use_cost_volume:
      cost_volume = compute_cost_volume(
          features1_normalized, warped2_normalized, max_displacement=4)
    else:
      concat_features = Concatenate(axis=-1)(
          [features1_normalized, warped2_normalized])
      cost_volume = self._cost_volume_surrogate_convs[level](concat_features)

    cost_volume = LeakyReLU(
        alpha=self._leaky_relu_alpha, dtype=self._dtype_policy)(
            cost_volume)

    if self._shared_flow_decoder:
      # This will ensure to work for arbitrary feature sizes per level.
      conv_1x1 = self._1x1_shared_decoder[level]
      features1 = conv_1x1(features1)

    # Compute context and flow from previous flow, cost volume, and features1.
    if flow_up is None:
      x_in = Concatenate(axis=-1)([cost_volume, features1])
    else:
      if context_up is None:
        x_in = Concatenate(axis=-1)([flow_up, cost_volume, features1])
      else:
        x_in = Concatenate(axis=-1)(
            [context_up, flow_up, cost_volume, features1])

    # Use dense-net connections.
    x_out = None
    if self._shared_flow_decoder:
      # reuse the same flow decoder on all levels
      flow_layers = self._flow_layers
    else:
      flow_layers = self._flow_layers[level]
    for layer in flow_layers[:-1]:
      x_out = layer(x_in)
      x_in = Concatenate(axis=-1)([x_in, x_out])
    context = x_out

    flow = flow_layers[-1](context)

    if (training and self._drop_out_rate):
      maybe_dropout = tf.cast(
          tf.math.greater(tf.random.uniform([]), self._drop_out_rate),
          tf.bfloat16 if self._use_bfloat16 else tf.float32)
      context *= maybe_dropout
      flow *= maybe_dropout

    if flow_up is not None and self._accumulate_flow:
      flow += flow_up

    # Upsample flow for the next lower level.
    flow_up = uflow_utils.upsample(flow, is_flow=True)
    if self._num_context_up_channels:
      context_up = self._context_up_layers[level](context)

    # Append results to list.
    flows.insert(0, flow)

  # Refine flow at level 1.
  refinement = self._refine_model([context, flow])
  if (training and self._drop_out_rate):
    refinement *= tf.cast(
        tf.math.greater(tf.random.uniform([]), self._drop_out_rate),
        tf.bfloat16 if self._use_bfloat16 else tf.float32)
  refined_flow = flow + refinement
  flows[0] = refined_flow
  return [tf.cast(flow, tf.float32) for flow in flows]
