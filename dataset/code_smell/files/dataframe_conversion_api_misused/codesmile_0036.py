# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_24/data_loader.py#L246-L305
# smelly line(s) in the original file: 254
# smelly line(s) in this file: 15
# ids: codesmile_0036
def __read_data__(self):
  # Standard scaler is used to scale data
  if self.scale:
    self.data_scaler = StandardScaler()
    self.label_scaler = StandardScaler()

  cols = pd.read_csv(self.cd_path, sep='\t', header=None)
  target_col = np.where(cols[1] == 'Label')[0][0]
  cat_cols = cols[cols[1] == 'Categ'][0].values
  train_x, train_y = self.read_file(self.train_path, target_col,
                                    self.header_in_data)
  test_x, test_y = self.read_file(self.test_path, target_col,
                                  self.header_in_data)
  # Divide the training data into trian and validation
  data = pd.concat([train_x, test_x])
  data[cat_cols] = data[cat_cols].apply(
      lambda x: x.astype('category').cat.codes)
  data = np.array(data).astype('float')
  labels = test_y
  valid_data = int(test_x.shape[0] * 0.1)
  train_x, test_x = data[:train_x.shape[0]], data[train_x.shape[0]:]
  valid_y, test_y = labels[:valid_data], labels[valid_data:]
  valid_x, test_x = test_x[:valid_data], test_x[valid_data:]
  cat_cols[cat_cols > target_col] = cat_cols[cat_cols > target_col] - 1

  # Scale data
  if self.scale:
    self.data_scaler.fit(train_x)
    train_x = self.data_scaler.transform(train_x)
    test_x = self.data_scaler.transform(test_x)
    valid_x = self.data_scaler.transform(valid_x)

    self.label_scaler.fit(train_y.reshape(-1, 1))
    train_y = self.label_scaler.transform(train_y.reshape(-1, 1))
    test_y = self.label_scaler.transform(test_y.reshape(-1, 1))
    valid_y = self.label_scaler.transform(valid_y.reshape(-1, 1))

  self.train_x = np.array(train_x, dtype=np.float64)
  self.train_y = np.array(train_y, dtype=np.float64)
  train_index = []
  for i in range(self.train_x.shape[0]):
    train_index.append(i)

  self.train_index = np.array(train_index)

  self.test_x = np.array(test_x, dtype=np.float64)
  self.test_y = np.array(test_y, dtype=np.float64)
  test_index = []
  for i in range(self.test_x.shape[0]):
    test_index.append(i)

  self.test_index = np.array(test_index)

  self.valid_x = np.array(valid_x, dtype=np.float64)
  self.valid_y = np.array(valid_y, dtype=np.float64)
  valid_index = []
  for i in range(self.valid_x.shape[0]):
    valid_index.append(i)

  self.valid_index = np.array(valid_index)
