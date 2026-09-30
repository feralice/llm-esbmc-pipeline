# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_93/utils.py#L28-L65
# smelly line(s) in the original file: 46, 47
# smelly line(s) in this file: 25, 26
# ids: codesmile_0191, codesmile_0192
def load_data(
    path_real: str,
    path_fake: str,
    real_sep: str = ",",
    fake_sep: str = ",",
    drop_columns: List = None,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    Load data from a real and synthetic data csv. This function makes sure that the loaded data has the same columns
    with the same data types.
    Args:
        path_real: string path to csv with real data
        path_fake: string path to csv with real data
        real_sep: separator of the real csv
        fake_sep: separator of the fake csv
        drop_columns: names of columns to drop.
    Return: Tuple with DataFrame containing the real data and DataFrame containing the synthetic data.
    """
    real = pd.read_csv(path_real, sep=real_sep, low_memory=False)
    fake = pd.read_csv(path_fake, sep=fake_sep, low_memory=False)
    if set(fake.columns.tolist()).issubset(set(real.columns.tolist())):
        real = real[fake.columns]
    elif drop_columns is not None:
        real = real.drop(drop_columns, axis=1)
        try:
            fake = fake.drop(drop_columns, axis=1)
        except:
            print(f"Some of {drop_columns} were not found on fake.index.")
        assert len(fake.columns.tolist()) == len(
            real.columns.tolist()
        ), f"Real and fake do not have same nr of columns: {len(fake.columns)} and {len(real.columns)}"
        fake.columns = real.columns
    else:
        fake.columns = real.columns

    for col in fake.columns:
        fake[col] = fake[col].astype(real[col].dtype)
    return real, fake
