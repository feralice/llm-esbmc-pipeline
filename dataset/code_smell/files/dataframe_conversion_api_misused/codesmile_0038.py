# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_23/util.py#L31-L37
# smelly line(s) in the original file: 35, 36
# smelly line(s) in this file: 11, 12
# ids: codesmile_0038, codesmile_0085
def create_dataset(dataset, window_size = 1):
    data_X, data_y = [], []
    df = pd.DataFrame(dataset)
    columns = [df.shift(i) for i in reversed(range(1, window_size+1))]
    data_X = pd.concat(columns, axis=1).dropna().values
    data_y = df.shift(-window_size).dropna().values
    return data_X, data_y
