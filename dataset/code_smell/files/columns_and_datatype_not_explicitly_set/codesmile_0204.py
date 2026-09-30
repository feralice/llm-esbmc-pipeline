# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_86/reader.py#L230-L312
# smelly line(s) in the original file: 244
# smelly line(s) in this file: 21
# ids: codesmile_0204
def load_dataseer_corpus_csv(filepath):
    """
    Load texts from the Dataseer dataset type corpus in csv format:

        doi,text,datatype,dataSubtype,leafDatatype

    Classification of the datatype follows a 3-level hierarchy, so the possible 3 classes are returned.
    dataSubtype and leafDatatype are optional

    Returns:
        tuple(numpy array, numpy array, numpy array, numpy array): 
            texts, datatype, datasubtype, leaf datatype

    """
    df = pd.read_csv(filepath)
    df = df[pd.notnull(df['text'])]
    if 'datatype' in df.columns:
        df = df[pd.notnull(df['datatype'])]
    if 'reuse' in df.columns:    
        df = df[pd.notnull(df['reuse'])]
    df.iloc[:,1].fillna('NA', inplace=True)

    # shuffle, note that this is important for the reuse prediction, the following shuffle in place
    # and reset the index
    df = df.sample(frac=1).reset_index(drop=True)

    texts_list = []
    for j in range(0, df.shape[0]):
        texts_list.append(df.iloc[j,1])

    if 'reuse' in df.columns:  
        # we simply get the reuse boolean value for the examples
        datareuses = df.iloc[:,2]
        reuse_list = datareuses.values.tolist()
        reuse_list = np.asarray(reuse_list)
        # map boolean values to [0,1]
        def map_boolean(x):
            return [1.0,0.0] if x == 'no_reuse' else [0.0,1.0]
        reuse_list = np.array(list(map(map_boolean, reuse_list)))
        print(reuse_list)
        return np.asarray(texts_list), reuse_list, None, None, ["no_reuse", "reuse"], None, None

    # otherwise we have the list of datatypes, and optionally subtypes and leaf datatypes
    datatypes = df.iloc[:,2]
    datatypes_list = datatypes.values.tolist()
    datatypes_list = np.asarray(datatypes_list)
    datatypes_list_lower = np.char.lower(datatypes_list)
    list_classes_datatypes = np.unique(datatypes_list_lower)    
    datatypes_final = normalize_classes(datatypes_list_lower, list_classes_datatypes)

    print(df.shape, df.shape[0], df.shape[1])

    if df.shape[1] > 3:
        # remove possible row with 'no_dataset'
        df = df[~df.datatype.str.contains("no_dataset")]
        datasubtypes = df.iloc[:,3]
        datasubtypes_list = datasubtypes.values.tolist()
        datasubtypes_list = np.asarray(datasubtypes_list)
        datasubtypes_list_lower = np.char.lower(datasubtypes_list)
        list_classes_datasubtypes = np.unique(datasubtypes_list_lower)
        datasubtypes_final = normalize_classes(datasubtypes_list_lower, list_classes_datasubtypes)

    '''
    if df.shape[1] > 4:
        leafdatatypes = df.iloc[:,4]
        leafdatatypes_list = leafdatatypes.values.tolist()
        leafdatatypes_list = np.asarray(leafdatatypes_list)
        #leafdatatypes_list_lower = np.char.lower(leafdatatypes_list)
        leafdatatypes_list_lower = leafdatatypes_list
        list_classes_leafdatatypes = np.unique(leafdatatypes_list_lower)  
        print(list_classes_leafdatatypes)
        leafdatatypes_final = normalize_classes(leafdatatypes_list_lower, list_classes_leafdatatypes)
    '''

    if df.shape[1] == 3:
        return np.asarray(texts_list), datatypes_final, None, None, list_classes_datatypes.tolist(), None, None
    #elif df.shape[1] == 4:
    else:
        return np.asarray(texts_list), datatypes_final, datasubtypes_final, None, list_classes_datatypes.tolist(), list_classes_datasubtypes.tolist(), None
    '''
    else:
        return np.asarray(texts_list), datatypes_final, datasubtypes_final, leafdatatypes_final, list_classes_datatypes.tolist(), list_classes_datasubtypes.tolist(), list_classes_leafdatatypes.tolist()
    '''
