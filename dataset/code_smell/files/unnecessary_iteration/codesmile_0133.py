# smell: Unnecessary Iteration (R17)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_94/corpus.py#L264-L315
# smelly line(s) in the original file: 285
# smelly line(s) in this file: 28
# ids: codesmile_0133
def read_corpus(language, max_rows=-1, max_length=1000000, lower=False,
                datasets_dir=None,
                raw_path=None):
  """Loads corpora."""
  # The "max_length" argument is the maximum sentence length (by tokens)
  # that we want to allow.
  #
  # "lower" is used for Middle Persian to reduce the heterograms to the
  # something more akin to the form that the scribes would have used (hence
  # only on the written side).
  source = "https://rws.xoba.com/.corpora/%s.tsv" % language
  if raw_path:
    source = raw_path
  elif datasets_dir:
    source = os.path.join(datasets_dir, language + ".tsv")
  print("Reading corpus from \"{}\" ...".format(source))
  with open(source, mode="r", encoding="utf-8") as f:
    data = pd.read_csv(f, sep="\t", header=None, dtype=str)
  print("Number of original verses in file: {}".format(data.shape[0]))
  table = {}
  nrows = 0
  for _, row in data.iterrows():
    try:
      verse, text = row[0], row[1]
      if pd.isnull(text):
        continue
      text_list = []
      for wp in text.split():
        wp = wp.split("/")
        if len(wp) == 2:
          w, p = wp
          if lower:
            w = w.lower()
          if "_" in p:  # Our output for the CMU dict
            p = p.split("_")
          else:
            p = list(p)
          text_list.append((w, p))
          text_list.append((" ", " "))
        else:
          text_list.append(wp)
          text_list.append(" ")
      if len(text_list) > max_length:
        continue
      table[verse] = text_list[:-1]
      nrows += 1
      if nrows == max_rows:
        break
    except ValueError:
      pass
  print("{}: Read {} rows".format(language, nrows))
  return table
