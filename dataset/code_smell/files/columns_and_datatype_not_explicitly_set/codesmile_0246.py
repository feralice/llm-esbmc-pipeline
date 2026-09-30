# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_2/clean.py#L46-L89
# smelly line(s) in the original file: 60, 61
# smelly line(s) in this file: 21, 22
# ids: codesmile_0246, codesmile_0247
def clean_dataset(dataset, attributes, centered):
    """Clean a dataset, given the filename for the dataset and the filename for the attributes.

    Args:
        :param dataset: Filename for dataset. The dataset should be formatted such that categorical
        variables use one-hot encoding
    and the label should be 0/1
        :param attributes: Filename for the attributes of the dataset. The file should have each column name in a list,
         and under this list should have 0 for an unprotected attribute, 1 for a protected attribute, and 2 for the
          attribute of the label.
        :param centered: boolean flag that determines whether to center the input covariates.
        :return X, X_prime, y: pandas dataframes of attributes, sensitive attributes, labels
    """

    df = pd.read_csv(dataset)
    sens_df = pd.read_csv(attributes)

    ## Get and remove label Y
    y_col = [str(c) for c in sens_df.columns if sens_df[c][0] == 2]
    print('label feature: {}'.format(y_col))
    if (len(y_col) > 1):
        raise ValueError('More than 1 label column used')
    if (len(y_col) < 1):
        raise ValueError('No label column used')

    y = df[y_col[0]]

    ## Do not use labels in rest of data
    X = df.loc[:, df.columns != y_col[0]]
    X = X.loc[:, X.columns != 'Unnamed: 0']
    ## Create X_prime, by getting protected attributes
    sens_cols = [str(c) for c in sens_df.columns if sens_df[c][0] == 1]
    print('sensitive features: {}'.format(sens_cols))
    sens_dict = {c: 1 if c in sens_cols else 0 for c in df.columns}
    X, sens_dict = one_hot_code(X, sens_dict)
    sens_names = [key for key in sens_dict.keys() if sens_dict[key] == 1]
    print(
        'there are {} sensitive features including derivative features'.format(
            len(sens_names)))
    X_prime = X[sens_names]
    if centered:
        X = center(X)
        X_prime = center(X_prime)
    return X, X_prime, y
