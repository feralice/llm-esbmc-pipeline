# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_2/clean.py#L147-L158
# smelly line(s) in the original file: 153, 154
# smelly line(s) in this file: 13, 14
# ids: codesmile_0248, codesmile_0249
def get_data(dataset):
    # Helper for main method
    """Given name of dataset, load in the three datasets associated from the clean.py file
    :param dataset:
    :return:
    """
    X = pd.read_csv('dataset/' + dataset + '_features.csv')
    X_prime = pd.read_csv('dataset/' + dataset + '_protectedfeatures.csv')
    y = pd.read_csv('dataset/' + dataset + '_labels.csv',
                    names=['index', 'label'])
    y = y['label']
    return X, X_prime, y
