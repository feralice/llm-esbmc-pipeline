# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_43/uflow_model.py#L309-L337
# smelly line(s) in the original file: 315
# smelly line(s) in this file: 13
# ids: codesmile_0021
def _build_flow_layers(self):
  """Build layers for flow estimation."""
  # Empty list of layers level 0 because flow is only estimated at levels > 0.
  result = [[]]
  for _ in range(1, self._num_levels):
    layers = []
    for c in [128, 128, 96, 64, 32]:
      layers.append(
          Sequential([
              Conv2D(
                  int(c * self._channel_multiplier),
                  kernel_size=(3, 3),
                  strides=1,
                  padding='same',
                  dtype=self._dtype_policy),
              LeakyReLU(
                  alpha=self._leaky_relu_alpha, dtype=self._dtype_policy)
          ]))
    layers.append(
        Conv2D(
            2,
            kernel_size=(3, 3),
            strides=1,
            padding='same',
            dtype=self._dtype_policy))
    if self._shared_flow_decoder:
      return layers
    result.append(layers)
  return result
