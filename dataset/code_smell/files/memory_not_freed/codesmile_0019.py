# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_43/uflow_model.py#L285-L294
# smelly line(s) in the original file: 287
# smelly line(s) in this file: 9
# ids: codesmile_0019
def _build_cost_volume_surrogate_convs(self):
  layers = []
  for _ in range(self._num_levels):
    layers.append(
        Conv2D(
            int(64 * self._channel_multiplier),
            kernel_size=(4, 4),
            padding='same',
            dtype=self._dtype_policy))
  return layers
