# smell: Chain Indexing (R20)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_2/clean.py#L104-L125
# smelly line(s) in the original file: 107
# smelly line(s) in this file: 10
# ids: codesmile_0190
def one_hot_code(df1, sens_dict):
    cols = df1.columns
    for c in cols:
        if isinstance(df1[c][0], str):
            column = df1[c]
            df1 = df1.drop(c, 1)
            unique_values = list(set(column))
            n = len(unique_values)
            if n > 2:
                for i in range(n):
                    col_name = '{}.{}'.format(c, i)
                    col_i = [
                        1 if el == unique_values[i] else 0 for el in column
                    ]
                    df1[col_name] = col_i
                    sens_dict[col_name] = sens_dict[c]
                del sens_dict[c]
            else:
                col_name = c
                col = [1 if el == unique_values[0] else 0 for el in column]
                df1[col_name] = col
    return df1, sens_dict
