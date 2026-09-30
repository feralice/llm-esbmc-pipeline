# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_24/data_loader.py#L227-L244
# smelly line(s) in the original file: 241
# smelly line(s) in this file: 21
# ids: codesmile_0214
def read_file(self, file_name, target_col, header_in_data):
  """Load dataframe and split into data and labels.

  Args:
   file_name: path to data file
   target_col: target column name
   header_in_data: data headers

  Returns:
   x: data in the form of numpy array
   y: labels in the form of numpy array

  """

  x = pd.read_csv(file_name, sep='\t', header=0 if header_in_data else None)
  y = x[target_col].values
  x.drop(target_col, axis=1, inplace=True)
  return x, y
