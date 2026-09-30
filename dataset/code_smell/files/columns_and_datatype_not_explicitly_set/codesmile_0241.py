# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_51/script_download_data.py#L428-L472
# smelly line(s) in the original file: 429
# smelly line(s) in this file: 8
# ids: codesmile_0241
def load_single_day(path, header, ids=None):
    df = pd.read_csv(path, header=None)
    df = df.rename(columns = lambda i: header[i])
    df.drop(columns=[c for c in df.columns if 'Lane' in c] + ['District'], inplace=True)
    if ids:
        df = df[df['Station'].isin(ids)]
    df['Timestamp'] = pd.to_datetime(df['Timestamp'])

    # Identify gaps in timelines
    num_gaps = 0
    all_timestamps = set(df['Timestamp'])
    interpolated = []
    groups = df.groupby('Station')
    for id, g in groups:
        if len(g) != len(g.dropna(subset=['Total Flow'])):
            _timestamps = set(g['Timestamp']).difference(set(g.dropna(subset=['Total Flow'])['Timestamp']))
            num_gaps += len(_timestamps)
            print(f'Found NaN in "Total Flow" at timestamps {_timestamps}')
            print('Interpolating...')

        diff = all_timestamps.difference(g['Timestamp'])
        if diff:
            num_gaps += len(diff)
            print(f'Missing observations ID {id} Timestamps: {diff}', file=sys.stderr)
            for elem in diff:
                g = g.append({'Timestamp':elem}, ignore_index=True)

        g = g.sort_values('Timestamp')
        g = g.interpolate(method='ffill')
        g = g.fillna(method = 'pad')
        interpolated.append(g)

    df = pd.concat(interpolated)
    if num_gaps:
        print(f'Missing {num_gaps/len(df) * 100}% of the data')

    # Add derived time info
    #df['Year'] = df['Timestamp'].apply(lambda x: x.year)
    df['Day of week'] = df['Timestamp'].apply(lambda x: x.dayofweek)
    df['Month'] = df['Timestamp'].apply(lambda x: x.month)
    df['Day'] = df['Timestamp'].apply(lambda x: x.day)
    df['Hour'] = df['Timestamp'].apply(lambda x: x.hour)
    df['Minute'] = df['Timestamp'].apply(lambda x: x.minute)

    return df
