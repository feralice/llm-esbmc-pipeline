# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_7/speech_synthesis.py#L53-L94
# smelly line(s) in the original file: 57
# smelly line(s) in this file: 11
# ids: codesmile_0245
def preprocess_data(self, file_path):
    """generate a list of tuples (wav_filename, wav_length_ms, transcript, speaker).
    """
    logging.info("Loading data from {}".format(file_path))
    lines = pd.read_csv(file_path,"\t")
    headers = lines.keys()
    lines_num = lines.shape[0]
    self.entries = []
    self.speakers = []
    for l in range(lines_num):
        wav_filename = lines["wav_filename"][l]
        wav_length = lines["wav_length_ms"][l]
        transcript = lines["transcript"][l]
        speaker = "global" if "speaker" not in headers else lines["speaker"][l]
        self.entries.append(
            tuple([wav_filename, wav_length, transcript, speaker])
        )
        if speaker not in self.speakers:
            self.speakers.append(speaker)

    speakers_ids = list(range(len(self.speakers)))
    self.speakers_dict = dict(zip(self.speakers, speakers_ids))
    self.speakers_ids_dict = dict(zip(speakers_ids, self.speakers))

    # handling special case for text_featurizer
    self.entries.sort(key=lambda item: len(item[2]))
    if self.text_featurizer.model_type == "text":
        _, _, all_transcripts, _, _ = zip(*self.entries)
        self.text_featurizer.load_model(all_transcripts)

    # apply some filter
    unk = self.text_featurizer.unk_index
    if self.hparams.remove_unk and unk != -1:
        self.entries = list(filter(lambda x: unk not in
                            self.text_featurizer.encode(x[2]), self.entries))
    self.entries = list(filter(lambda x: len(x[2]) in
                        range(self.hparams.input_length_range[0],
                        self.hparams.input_length_range[1]), self.entries))
    self.entries = list(filter(lambda x: float(x[1]) in
                        range(self.hparams.output_length_range[0],
                        self.hparams.output_length_range[1]), self.entries))
    return self
