# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_86/reader.py#L42-L69
# smelly line(s) in the original file: 67
# smelly line(s) in this file: 32
# ids: codesmile_0072
def load_texts_and_classes_pandas(filepath):
    """
    Load texts and classes from a file in csv format using pandas dataframe, with format as follow:

    id      text    class_0     ... class_n
    id_0    text_0  class_00    ... class_n0
    id_1    text_1  class_01    ... class_n1
    ...
    id_m    text_m  class_0m    ... class_nm

    It should support any CSV file format.

    Returns:
        tuple(numpy array, numpy array): texts and classes

    """

    df = pd.read_csv(filepath)
    df.iloc[:,1].fillna('MISSINGVALUE', inplace=True)

    texts_list = []
    for j in range(0, df.shape[0]):
        texts_list.append(df.iloc[j,1])

    classes = df.iloc[:,2:]
    classes_list = classes.values.tolist()

    return np.asarray(texts_list), np.asarray(classes_list)
