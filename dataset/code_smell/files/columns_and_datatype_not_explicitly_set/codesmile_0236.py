# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_51/script_download_data.py#L110-L173
# smelly line(s) in the original file: 122
# smelly line(s) in this file: 19
# ids: codesmile_0236
def download_electricity(data_folder):
    """Downloads electricity dataset from UCI repository."""

    url = "https://archive.ics.uci.edu/static/public/321/electricityloaddiagrams20112014.zip"

    csv_path = os.path.join(data_folder, "LD2011_2014.txt")
    zip_path = csv_path + ".zip"

    download_and_unzip(url, zip_path, csv_path, data_folder)

    print("Aggregating to hourly data")

    df = pd.read_csv(csv_path, index_col=0, sep=";", decimal=",")
    df.index = pd.to_datetime(df.index)
    df.sort_index(inplace=True)

    # Used to determine the start and end dates of a series
    output = df.resample("1h").mean().replace(0.0, np.nan)

    earliest_time = output.index.min()
    # Filter to match range used by other academic papers
    output = output[(output.index >= '2014-01-01') & (output.index < '2014-09-08')]

    df_list = []
    for label in output:
        srs = output[label]

        if srs.isna().all():
            continue

        start_date = min(srs.fillna(method="ffill").dropna().index)
        end_date = max(srs.fillna(method="bfill").dropna().index)

        srs = output[label].fillna(0.0)

        tmp = pd.DataFrame({"power_usage": srs})
        date = tmp.index
        tmp["t"] = (date - earliest_time).seconds / 60 / 60 + (
            date - earliest_time
        ).days * 24
        tmp["days_from_start"] = (date - earliest_time).days
        tmp["categorical_id"] = label
        tmp["date"] = date
        tmp["id"] = label
        tmp["hour"] = date.hour
        tmp["day"] = date.day
        tmp["day_of_week"] = date.dayofweek
        tmp["month"] = date.month
        tmp["power_usage_weight"] = ((date >= start_date) & (date <= end_date))

        df_list.append(tmp)

    output = pd.concat(df_list, axis=0, join="outer").reset_index(drop=True)

    output["categorical_id"] = output["id"].copy()
    output["hours_from_start"] = output["t"]
    output["categorical_day_of_week"] = output["day_of_week"].copy()
    output["categorical_hour"] = output["hour"].copy()
    output["power_usage_weight"] = output["power_usage_weight"].apply(lambda b: 1 if b else 0)


    output.to_csv(data_folder + "/electricity.csv")

    print("Done.")
