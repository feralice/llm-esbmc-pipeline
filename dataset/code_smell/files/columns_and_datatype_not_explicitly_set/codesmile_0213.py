# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_24/data_loader.py#L102-L204
# smelly line(s) in the original file: 109
# smelly line(s) in this file: 14
# ids: codesmile_0213
def __read_data__(self):

  # Standard scaler is used to scale data
  if self.scale:
    self.scaler = StandardScaler()
  # Loading dataset
  data_path = os.path.join(self.root_path, 'ECL.csv')
  inputs = pd.read_csv(data_path)
  inputs.fillna(method='ffill', inplace=True)
  inputs = reduce_mem_usage(inputs)

  # Dividing dataset into Training, Testing and Validation
  total_number_of_hours = inputs.shape[0]
  training_hours = int(inputs.shape[0] * 0.7)
  testing_hours = int(inputs.shape[0] * 0.2)
  validation_hours = total_number_of_hours - training_hours - testing_hours

  train_x = []
  train_y = []
  train_index = []

  valid_x = []
  valid_y = []
  valid_index = []

  test_x = []
  test_y = []
  test_index = []

  if self.features == 'S':
    train_sample_index = 0
    test_sample_index = 0
    val_sample_index = 0

    # Every customer (an entire time series) divide the customer data
    # into training/testing/validation,
    # Scale indpendently since customers have very different behaviors
    # Create time series based on the sequence and prediction length
    for i in range(1, self.num_ts):

      data = inputs.values[:, i]
      data = data.reshape(-1, 1)
      if self.scale:
        train_data = np.array(data[:training_hours, :], dtype=np.float64)
        self.scaler.fit(train_data)
        df_data = self.scaler.transform(data)
      else:
        df_data = np.array(data, dtype=np.float64)

      index = 0
      for j in range(index, training_hours - self.pred_len - self.seq_len):

        s_begin = j
        s_end = s_begin + self.seq_len
        r_begin = s_end
        r_end = r_begin + self.pred_len
        train_x.append(df_data[s_begin:s_end, :])
        train_y.append(df_data[r_begin:r_end, 0].reshape(-1, 1))
        train_index.append(train_sample_index)
        train_sample_index += 1

      index = training_hours - self.pred_len - self.seq_len
      for j in range(
          index,
          validation_hours + training_hours - self.pred_len - self.seq_len):

        s_begin = j
        s_end = s_begin + self.seq_len
        r_begin = s_end
        r_end = r_begin + self.pred_len

        valid_x.append(df_data[s_begin:s_end, :])
        valid_y.append(df_data[r_begin:r_end, 0].reshape(-1, 1))
        valid_index.append(val_sample_index)
        val_sample_index += 1

      index = validation_hours + training_hours - self.pred_len - self.seq_len
      for j in range(
          index, testing_hours + validation_hours + training_hours -
          self.pred_len - self.seq_len):
        s_begin = j
        s_end = s_begin + self.seq_len
        r_begin = s_end
        r_end = r_begin + self.pred_len
        test_x.append(df_data[s_begin:s_end, :])
        test_y.append(df_data[r_begin:r_end, 0].reshape(-1, 1))
        test_index.append(test_sample_index)
        test_sample_index += 1
  else:
    # Electricity is a univariate dataset
    raise NotImplementedError

  self.train_x = np.array(train_x, dtype=np.float16)
  self.train_y = np.array(train_y, dtype=np.float16)
  self.train_index = np.array(train_index)

  self.valid_x = np.array(valid_x, dtype=np.float16)
  self.valid_y = np.array(valid_y, dtype=np.float16)
  self.valid_index = np.array(valid_index)

  self.test_x = np.array(test_x, dtype=np.float16)
  self.test_y = np.array(test_y, dtype=np.float16)
  self.test_index = np.array(test_index)
