# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_39/gen_tstatistic.py#L136-L155
# smelly line(s) in the original file: 151
# smelly line(s) in this file: 22
# ids: codesmile_0244
def read_all_eval_subdir(data_directory):
  """Aggregate metrics across shards.

  Args:
    data_directory: pathway to class level metrics csv.

  Returns:
    A pandas dataframe with all imported records.
  """

  filenames = tf.gfile.Glob(data_directory + '/' + '*.csv')

  df = []
  for filename in filenames:
    with tf.gfile.Open(filename) as f:
      df_ = pd.read_csv(f)
      df.append(df_)

  df_ = pd.concat(df, ignore_index=False)
  return df_
