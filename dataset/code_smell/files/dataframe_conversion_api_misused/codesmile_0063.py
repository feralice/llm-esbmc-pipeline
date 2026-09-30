# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_56/time_series.py#L147-L154
# smelly line(s) in the original file: 154
# smelly line(s) in this file: 14
# ids: codesmile_0063
def is_between_dates(dates, start=None, end=None):
  """Return boolean indices indicating if dates occurs between start and end."""
  if start is None:
    start = pd.to_datetime(0)
  if end is None:
    end = pd.to_datetime(sys.maxsize)
  date_series = pd.Series(pd.to_datetime(dates))
  return date_series.between(start, end).values
