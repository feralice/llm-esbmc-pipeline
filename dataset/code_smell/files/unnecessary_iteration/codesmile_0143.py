# smell: Unnecessary Iteration (R17)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/5/files/EvalID_79/protseq_analysis.py#L654-L676
# smelly line(s) in the original file: 661
# smelly line(s) in this file: 14
# ids: codesmile_0143
def make_plot_df(cycle_df):
  targets = []
  base_targets = []
  partners = []
  fracs = []
  counts = []
  cols = list(cycle_df.columns)[:-1]
  for _, row in cycle_df.iterrows():
    row_sum = row[cols].sum()
    for col in cols:
      partners.append(row["binder"])
      targets.append(col)
      base_targets.append(col.split(".")[0].split("_")[0])
      counts.append(row[col])
      fracs.append(row[col] / row_sum)
  plot_df = pd.DataFrame.from_dict({
      "target": targets,
      "Binder for": partners,
      "Binder Target": base_targets,
      "Count": counts,
      "Count Fraction": fracs
  })
  return plot_df
