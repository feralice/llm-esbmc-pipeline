# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_17/ukb.py#L287-L574
# smelly line(s) in the original file: 518
# smelly line(s) in this file: 238
# ids: codesmile_0251
def join_tfrecord_csv(path_simulations,
                      input_prefix,
                      path_input,
                      path_output,
                      output_prefix = 'train_features'):
  """Join TFRecord files and a csv file with a common id.

  Args:
    path_simulations: path for csv file
    input_prefix: prefix of TFRecords
    path_input: path to TFRecords
    path_output: path to save TFRecors (should be differet to avoid overwrite)
    output_prefix: prefix of joined TFRecords
  """

  def _to_basename(path):
    path = path.split('/')[-1]
    return path.split('_')[0]

  def _get_value_key(field_name):
    """Returns an output-formatted TFRecord value key for `field_name`."""
    return os.path.join('image', field_name, 'value')

  def _get_weight_key(field_name):
    """Returns an output-formatted TFRecord weight key for `field_name`."""
    image_prefix = 'image/'
    weight_suffix = '/value'
    return f'{image_prefix}{field_name}{weight_suffix}'

  def _build_ukb_tfrecord_features():
    """Returns a feature dictionary used to parse TFRecord examples.

    We assume that the UKB TFRecords are defined using the following schema:

      1. An encoded image with key `IMAGE_ENCODED_TFR_KEY` that can be decoded
         using `tf.image.decode_png`.
      2. A unique identifier for each image with key `IMAGE_ID_TFR_KEY`.

    The `tf.io.parse_single_example` function uses the resulting feature
    dictionary to parse each TFRecord.

    Returns:
      A feature dictionary for parsing TFRecords.
    """
    image_prefix = 'image/'
    image_id_tfr_key = f'{image_prefix}id'
    image_encoded_tfr_key = f'{image_prefix}encoded'
    features = {}
    features[image_encoded_tfr_key] = tf.io.FixedLenFeature([], tf.string)
    features[image_id_tfr_key] = tf.io.FixedLenFeature([1], tf.string)
    return features

  def _get_parse_example_fn(features):
    """Returns a function that parses a TFRecord example using `features`."""

    def _parse_example(example):
      return tf.io.parse_single_example(example, features)

    return _parse_example

  def _field_to_keys(
      field,
      delimiter = ':'):
    """Returns a label column field's base field name, value key, and weight key.

    For example, given `glaucoma_gradability:GRADABLE`, this function returns a
    triple containing `glaucoma_gradability`, image/glaucoma_gradability/value`,
    and `image/glaucoma_gradability/weight`.

    Note: We handle the following set of special fields differently. This subset
    of fields may not have an associated value or weight key:
      - eid: field='eid', value_key='eid', weight_key=None
      - image_id: field='image_id', value_key='image/id', weight_key=None

    Args:
      field: A prediction column field.
      delimiter: The delimiter used to split the field into the base field name
        and the field value.

    Returns:
      The field's base field name, value key, and weight key.
    """
    image_id_pred_key = 'image_id'
    eid = 'eid'
    special_cases = {image_id_pred_key, eid}
    if field in special_cases:
      if field == eid:
        return field, None
      return image_id_pred_key, None

    if delimiter not in field:
      ValueError(f'Unexpected field format: {field}')
    try:
      field_name, _ = field.split(delimiter)
    except ValueError:
      field_name = field.split(delimiter)
    field_name = field_name[0]
    return _get_value_key(field_name), _get_weight_key(field_name)

  def _map_id_to_encoded_image(ds):
    """Convert a `tf.data.Dataset` containing images and ids to a tensor dict."""
    ids_to_encoded = {}
    image_prefix = 'image/'
    image_id_tfr_key = f'{image_prefix}id'
    image_encoded_tfr_key = f'{image_prefix}encoded'
    for example in ds:
      image_id = example[image_id_tfr_key].numpy()[0].decode('utf-8')
      image_id = _to_basename(image_id)
      image_encoded = example[image_encoded_tfr_key]
      ids_to_encoded[image_id] = image_encoded
    return ids_to_encoded

  def _map_ukb_id_to_encoded_images(
      ukb_tfrecord_path):
    """Returns a dictionary of encoded image tensors keyed on image id."""
    # Load and parse the TFRecords located at `ukb_tfrecord_path`.
    outcome_features = _build_ukb_tfrecord_features()
    tfrecord_ds = tf.data.TFRecordDataset(filenames=ukb_tfrecord_path)
    parsed_tfrecord_ds = tfrecord_ds.map(
        _get_parse_example_fn(outcome_features),
        num_parallel_calls=tf.data.AUTOTUNE)
    # Build a map of image ids to encoded image tensors.
    id_to_encoded_images = _map_id_to_encoded_image(parsed_tfrecord_ds)
    return id_to_encoded_images

  def _record_to_tensor_dict(label_record):
    """Converts a CSV label record to the expected tensor dictionary format."""

    filtered_record = label_record.keys()
    # Initialize empty arrays of the expected field size so that we can set the
    # value of each head's prediction at the corresponding index.
    # Since we have predictions for all record fields, we set the sample
    # weight to `1.0` for all records.
    tf_dict = {}
    for field in filtered_record:
      value_key, weight_key = _field_to_keys(field)
      tf_dict[value_key] = [None]
      if weight_key:
        tf_dict[weight_key] = [1.0]

    # Populate each key at the given index.
    for field, value in label_record.items():
      value_key, weight_key = _field_to_keys(field)
      tf_dict[value_key][0] = value

    # Assert that we have populated all expected field indices.
    for field, value in tf_dict.items():
      assert None not in value
    return tf_dict

  def _build_label_tensor_dicts(id_to_encoded_images, label_records):
    """Converts label records w/ids in `id_to_encoded_images` to tensor dicts."""
    tensor_dicts = []
    for first_name in id_to_encoded_images:
      if first_name not in label_records:
        continue
      record = label_records[first_name]
      tensor_dicts.append(_record_to_tensor_dict(record))

    return tensor_dicts

  def _tf_dict_to_example(tf_dict, encoded_image):
    """Merges a tensor dict and the encoded image into a `tf.train.Example`."""
    example = tf.train.Example()
    image_prefix = 'image/'
    image_id_tfr_key = f'{image_prefix}id'
    image_encoded_tfr_key = f'{image_prefix}encoded'
    eid = 'eid'
    for key, value in tf_dict.items():
      if key in {image_id_tfr_key, eid}:
        example.features.feature[key].bytes_list.value.append(
            str(value[0]).encode('utf-8'))
      else:
        example.features.feature[key].float_list.value.extend(value)
    example.features.feature[image_encoded_tfr_key].bytes_list.value.append(
        encoded_image.numpy())
    return example

  def _convert_tensor_dicts_to_examples(
      records,
      id_to_encoded_images):
    """Converts a list of tensor dict records to `tf.train.Example`s."""
    examples = []
    image_prefix = 'image/'
    image_id_tfr_key = f'{image_prefix}id'
    for record in records:
      image_basename = _to_basename(record[image_id_tfr_key][0])
      encoded_image = id_to_encoded_images[image_basename]
      examples.append(_tf_dict_to_example(record, encoded_image))
    return examples

  def _write_tf_examples(tf_examples, output_path):
    """Writes a list of `tf.train.Example`s as TFRecords the `output_path`."""
    with tf.io.TFRecordWriter(str(output_path)) as writer:
      for example in tf_examples:
        writer.write(example.SerializeToString())

  def _print_status(status,
                    tfrecord_path,
                    output_path,
                    error = None):
    """Prints the update status for the given paths."""
    lines = [
        f'\nTFRecord update {status}:'
        f'\n\ttfrecord_path="{tfrecord_path}"',
        f'\n\toutput_path="{output_path}"',
    ]
    if error:
      lines.append(f'\n\terror=\n{error}')

  def _add_labels_to_tfrecords(tfrecord_path, output_path,
                               label_records, overwrite=True):
    """Runs the pipeline, constructing new labeled UKB TFRecords."""
    # Only regenerate existing TFRecords if `overwrite==True`.
    if os.path.exists(str(output_path)) and not overwrite:
      _print_status('SKIPPED (`output_path` already exists)', tfrecord_path,
                    output_path)
      return
    try:
      id_to_encoded_images = _map_ukb_id_to_encoded_images(tfrecord_path)
      label_tfrecords = _build_label_tensor_dicts(id_to_encoded_images,
                                                  label_records)
      tf_examples = _convert_tensor_dicts_to_examples(label_tfrecords,
                                                      id_to_encoded_images)
      _write_tf_examples(tf_examples, output_path)
      _print_status('completed successfully', tfrecord_path, output_path)
    except ValueError:
      _print_status('FAILED', tfrecord_path, output_path)
      return tfrecord_path

  with gfile.GFile(path_simulations) as f:
    features = pd.read_csv(f)

  if path_input == path_output:
    raise ValueError('Input and Output path should be different!')

  # Global variable inside this function
  label_records = {
      _to_basename(record['image_id']): record
      for record in features.to_dict('records')
  }

  # Fetch the set of UKB input TFRecord shards.
  try:
    ukb_tfrecord_input_filenames = [
        filename for filename in os.listdir(str(path_input))
        if filename.startswith(input_prefix)
    ]
  except FileNotFoundError:
    ukb_tfrecord_input_filenames = [
        filename for filename in gfile.listdir(str(path_input))
        if filename.startswith(input_prefix)
    ]

  ukb_tfrecord_input_filepaths = [
      path_input + '/' + filename for filename in ukb_tfrecord_input_filenames
  ]
  ukb_tfrecord_output_filenames: List[str] = [
      filename.replace(input_prefix, output_prefix)
      for filename in ukb_tfrecord_input_filenames
  ]
  ukb_tfrecord_output_filepaths: List[pathlib.Path] = [
      path_output +'/'+ filename
      for filename in ukb_tfrecord_output_filenames
  ]
  # Generate arguments for converting each shard.
  add_labels_to_tfrecords_args1 = []
  add_labels_to_tfrecords_args2 = []

  for tfrecord_path, output_path in zip(ukb_tfrecord_input_filepaths,
                                        ukb_tfrecord_output_filepaths):
    add_labels_to_tfrecords_args1.append(tfrecord_path)
    add_labels_to_tfrecords_args2.append(output_path)

  # Process each shard in parallel, pairing images and labels.
  with concurrent.futures.ThreadPoolExecutor(max_workers=40) as executor:
    failed_paths_with_none = list(
        executor.map(_add_labels_to_tfrecords,
                     add_labels_to_tfrecords_args1,
                     add_labels_to_tfrecords_args2,
                     label_records))

  # Print the filepaths of any failed runs for reprocessing.
  failed_paths = [str(path) for path in failed_paths_with_none if path]
  if failed_paths:
    failed_path_str = '\n\t'.join([''] + failed_paths)
    print(f'The following TFRecord updates failed:{failed_path_str}')
  print('DONE with JOIN features')
