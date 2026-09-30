# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_23/util.py#L39-L73
# smelly line(s) in the original file: 59, 62
# smelly line(s) in this file: 27, 30
# ids: codesmile_0039, codesmile_0040
def load_data(data_file_url, window_size):
    """Loads data into preprocessed (train_X, train_y, eval_X, eval_y) dataframes.

    Returns:
      A tuple (train_X, train_y, eval_X, eval_y), where train_X and eval_X are
      Pandas dataframes with features for training and train_y and eval_y are
      numpy arrays with the corresponding labels.
    """
    # The % of data we should use for training
    TRAINING_SPLIT = 0.8

    # Download CSV and import into Pandas DataFrame
    file_stream = file_io.FileIO(data_file_url, mode='r')
    df = pd.read_csv(StringIO(file_stream.read()))
    df.index = df[df.columns[0]]
    df = df[['count']]

    scaler = StandardScaler()

    # Time series: split latest data into test set
    train = df.values[:int(TRAINING_SPLIT * len(df)), :]
    print(train)
    train = scaler.fit_transform(train)
    test = df.values[int(TRAINING_SPLIT * len(df)):, :]
    test = scaler.transform(test)

    # Create test and training sets
    train_X, train_y = create_dataset(train, window_size)
    test_X, test_y = create_dataset(test, window_size)

    # Reshape input data
    train_X = np.reshape(train_X, (train_X.shape[0], 1, train_X.shape[1]))
    test_X = np.reshape(test_X, (test_X.shape[0], 1, test_X.shape[1]))

    return train_X, train_y, test_X, test_y
