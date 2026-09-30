# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_12/build_numpy_cache.py#L108-L143
# smelly line(s) in the original file: 133
# smelly line(s) in this file: 32
# ids: codesmile_0193
def build_cache(*,
                filename: str = 'IBM_unadjusted.txt',
                url: str = 'http://api.kibot.com/?action=history&symbol=IBM&interval=1&unadjusted=0&bp=1&user=guest',
                force_download: bool = False):
    data_path = lab.get_data_path() / filename
    data_with_header = lab.get_data_path() / 'stocks.csv'

    if not lab.get_data_path().exists():
        lab.get_data_path().mkdir(parents=True)

    if force_download or not data_path.exists():
        data_with_header.unlink(True)
        with monit.section('Download data') as s:
            def reporthook(count, block_size, total_size):
                s.progress(count * block_size / total_size)

            urllib.request.urlretrieve(url, str(data_path), reporthook=reporthook)

    if not data_with_header.exists():
        with open(str(data_with_header), 'w') as fh:
            fh.write('Date,Time,Open,High,Low,Close,Volume\n')
            with open(str(data_path), 'r') as f:
                fh.write(f.read())

    with monit.section("Read data"):
        df = pd.read_csv(str(data_with_header))
    df = parse(df)
    with monit.section("Filter pre-market data"):
        df = filter_premarket(df)

    with monit.section("To numpy"):
        dates, packets = to_numpy(df)

    with monit.section("Save"):
        np.save(str(lab.get_data_path() / "packets.npy"), packets)
        np.save(str(lab.get_data_path() / "dates.npy"), dates)
