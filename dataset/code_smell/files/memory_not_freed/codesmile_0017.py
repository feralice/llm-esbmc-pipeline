# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_43/uflow_model.py#L86-L128
# smelly line(s) in the original file: 120
# smelly line(s) in this file: 41
# ids: codesmile_0017
def compute_cost_volume(features1, features2, max_displacement):
  """Compute the cost volume between features1 and features2.

  Displace features2 up to max_displacement in any direction and compute the
  per pixel cost of features1 and the displaced features2.

  Args:
    features1: tf.tensor of shape [b, h, w, c]
    features2: tf.tensor of shape [b, h, w, c]
    max_displacement: int, maximum displacement for cost volume computation.

  Returns:
    tf.tensor of shape [b, h, w, (2 * max_displacement + 1) ** 2] of costs for
    all displacements.
  """

  # Set maximum displacement and compute the number of image shifts.
  _, height, width, _ = features1.shape.as_list()
  if max_displacement <= 0 or max_displacement >= height:
    raise ValueError(f'Max displacement of {max_displacement} is too large.')

  max_disp = max_displacement
  num_shifts = 2 * max_disp + 1

  # Pad features2 and shift it while keeping features1 fixed to compute the
  # cost volume through correlation.

  # Pad features2 such that shifts do not go out of bounds.
  features2_padded = tf.pad(
      tensor=features2,
      paddings=[[0, 0], [max_disp, max_disp], [max_disp, max_disp], [0, 0]],
      mode='CONSTANT')
  cost_list = []
  for i in range(num_shifts):
    for j in range(num_shifts):
      corr = tf.reduce_mean(
          input_tensor=features1 *
          features2_padded[:, i:(height + i), j:(width + j), :],
          axis=-1,
          keepdims=True)
      cost_list.append(corr)
  cost_volume = tf.concat(cost_list, axis=-1)
  return cost_volume
