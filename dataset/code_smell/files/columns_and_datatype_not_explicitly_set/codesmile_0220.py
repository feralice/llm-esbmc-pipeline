# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_22/ppca.py#L234-L525
# smelly line(s) in the original file: 240
# smelly line(s) in this file: 13
# ids: codesmile_0220
def main(_):
  print("Loading data...")
  dfs = []
  for filename in os.listdir(FLAGS.data):
    if filename.endswith(".csv"):
      dfs.append(
          pd.read_csv(os.path.join(FLAGS.data, filename), encoding="utf-8"))
  data = pd.concat(dfs)
  print("%d Examples" % (len(set(data["id"]))))
  print("%d Annotations" % len(data))

  if not os.path.isdir(FLAGS.plot_dir):
    os.makedirs(FLAGS.plot_dir)

  with open(FLAGS.emotion_file, "r") as f:
    all_emotions = f.read().splitlines()
  all_emotions_neutral = all_emotions + ["neutral"]
  emotion2idx = {e: i for i, e in enumerate(all_emotions)}
  print("%d emotion Categories" % len(all_emotions))

  print("Processing data...")

  # Remove neutral labels
  data = data[data["neutral"] == 0]

  # Remove examples with no ratings (difficult examples)
  data = data[data[all_emotions_neutral].sum(axis=1) != 0]

  # Convert into num_examples x num_raters x num_ratings format
  data = data.groupby("id").filter(lambda x: len(x) >= 3)
  id_groups = data.groupby("id")

  worker2examples = {}  # dict mapping worker ids to (example, rater id) tuples
  max_num_raters = data.groupby("id").size().max()
  ratings = np.zeros(
      (len(id_groups), max_num_raters, len(all_emotions)))  # ignore "neutral"
  rater_msk = np.zeros(
      (len(id_groups), max_num_raters))  # for masking out non-existent raters
  print("Ratings shape", ratings.shape)

  # Get ratings and rater mask
  texts = []
  for ex_idx, (_, g) in enumerate(id_groups):
    texts.append(g.iloc[0]["text"])
    rater_count = 0

    # iterate through workers
    for _, row in g.iterrows():
      for e in all_emotions:
        ratings[ex_idx, rater_count, emotion2idx[e]] = row[e]
        rater_msk[ex_idx, rater_count] = 1

      worker_id = row["rater_id"]
      if worker_id in worker2examples:
        worker2examples[worker_id].append((ex_idx, rater_count))
      else:
        worker2examples[worker_id] = [(ex_idx, rater_count)]
      rater_count += 1

  print("Calculating leave-out (partial) correlations...")
  partial_corr_per_rater = []
  corr_per_rater = []
  for worker_id in worker2examples:
    partial_corrs, corrs = LeaveOut(ratings, rater_msk, worker2examples,
                                    worker_id)
    if len(partial_corrs) < len(all_emotions):
      continue

    partial_corr_per_rater.append(partial_corrs)
    corr_per_rater.append(corrs)
  corr_per_rater = np.array(corr_per_rater)
  partial_corr_per_rater = np.array(partial_corr_per_rater)

  # Verify that there are no NaN values
  assert np.isnan(corr_per_rater).sum() == 0

  # Apply Wilcoxon signed rank test to test significance of each dimension
  p_vals = np.apply_along_axis(wilcoxon, 0, partial_corr_per_rater)[1]

  # Apply Bonferroni correction
  reject, corr_pvals, _, newalpha = multipletests(
      p_vals, alpha=0.05, method="bonferroni")
  print("Which dimensions to keep?")
  print(reject)
  print(corr_pvals)
  print(newalpha)

  print("Running PPCA on all the data...")
  # Take all raters and split them randomly
  x = []
  y = []
  rater_counts = rater_msk.sum(axis=1).astype(int)
  all_ratings_avg = []
  for i, ex in enumerate(ratings):
    # Get actual raters based on mask
    keep = []
    for worker_rating in ex[:rater_counts[i]]:
      keep.append(list(worker_rating))
    all_ratings_avg.append(list(np.array(keep).mean(axis=0)))

    # Shuffle raters randomly
    random.shuffle(keep)

    num_raters = len(keep)
    x.append(list(np.array(keep[:int(num_raters / 2)]).mean(axis=0)))
    y.append(list(np.array(keep[int(num_raters / 2):]).mean(axis=0)))

  x = np.array(x)
  y = np.array(y)
  all_ratings_avg = np.array(all_ratings_avg)
  w, v = PPCA(x, y)  # final components (p-values determine which ones to keep)

  print("Plotting percentage of covariance explained...")
  PlotCovar(v)

  # Apply varimax rotation
  w_vari = Varimax(w)

  # Get mapping between ppcs and emotions
  map_df = pd.DataFrame(
      w_vari, index=all_emotions, columns=np.arange(len(all_emotions))).round(4)
  # Sort to move values to diagonal
  map_df = map_df[list(
      np.argsort(map_df.apply(lambda x: pd.Series.nonzero(x)[0]).values)[0])]
  f = plt.figure(figsize=(10, 6), dpi=300)
  sns.heatmap(
      map_df,
      center=0,
      cmap=sns.diverging_palette(240, 10, n=50),
      yticklabels=all_emotions)
  plt.xlabel("Component")
  plt.savefig(
      FLAGS.plot_dir + "/component_loadings.pdf",
      dpi=600,
      format="pdf",
      bbox_inches="tight")
  ppc2emotion = map_df.abs().idxmax().to_dict()
  emotion2ppc = {e: i for i, e in ppc2emotion.items()}
  print(ppc2emotion)

  print("Plotting frequency and mean left-out rater correlations...")
  corr_mean = corr_per_rater.mean(axis=0)
  corr_mean_ordered = [corr_mean[emotion2ppc[e]] for e in all_emotions]
  df_plot = pd.DataFrame({
      "emotion": all_emotions,
      "agreement": corr_mean_ordered
  })
  df_plot["count"] = df_plot["emotion"].map(
      data[all_emotions].sum(axis=0).to_dict())
  df_plot.sort_values("count", ascending=False, inplace=True)
  df_plot.to_csv(FLAGS.plot_dir + "/emotion_agreements.csv", index=False)

  # Get colors
  norm = plt.Normalize(df_plot["agreement"].min(), df_plot["agreement"].max())
  sm = plt.cm.ScalarMappable(cmap="BuPu", norm=norm)
  sm.set_array([])

  # Generate figure
  fig = plt.figure(dpi=600, figsize=(5, 6))
  ax = sns.barplot(
      data=df_plot,
      y="emotion",
      x="count",
      orient="h",
      hue="agreement",
      palette="BuPu",
      dodge=False,
      edgecolor="black",
      linewidth=1)
  ax.get_legend().remove()
  ax.figure.colorbar(sm)
  plt.text(18000, 31, "Interrater\nCorrelation", ha="center")
  plt.xlabel("Number of Examples")
  plt.ylabel("")
  plt.draw()
  labels = [item.get_text() for item in ax.get_xticklabels()]
  ax.set_xticklabels(["%dk" % (int(int(label) / 1000)) for label in labels])
  plt.tight_layout()
  fig.savefig(
      FLAGS.plot_dir + "/label_distr_agreement.pdf",
      dpi=600,
      format="pdf",
      bbox_inches="tight")

  print("Generating t-SNE plot...")
  # Get PPC scores for all examples
  all_ratings_avg = Demean(all_ratings_avg)  # demean all ratings
  ppc_scores = all_ratings_avg.dot(w_vari)  # project onto ppcs
  ppc_scores_abs = np.absolute(ppc_scores)

  # Load maximally distinct colors
  colors = pd.read_csv(
      FLAGS.rgb_colors, sep="\t", header=None, names=np.arange(3))

  # Set colors (todo(ddemszky): add names to colors in file)
  palette_rgb = colors.values
  with open(FLAGS.emotion_color_order) as f:
    color_order = f.read().splitlines()
  ppc2color = {emotion2ppc[e]: i for i, e in enumerate(color_order)}
  # get rgb value for each example based on weighted average of top emotions
  rgb_vals = []
  hex_vals = []
  top_categories = []
  threshold = 0.5  # exclude points not loading on any of the top 10 categories
  counter = 0
  rgb_max = 255
  other_color = palette_rgb[len(all_emotions), :]
  for i, scores in enumerate(ppc_scores_abs):

    top_ppcs = [
        idx for idx in (-scores).argsort()[:2] if scores[idx] > threshold
    ]
    top_emotions = ",".join([ppc2emotion[idx] for idx in top_ppcs
                            ]) if top_ppcs else "other"
    top_categories.append(top_emotions)
    if len(top_ppcs) < 1:  # doesn't have top emotions from list
      color = other_color  # use grey
      counter += 1
    else:
      # Weighted average of top emotions (square->weighted average->square root)
      color_ids = [ppc2color[idx] for idx in top_ppcs]
      weights = [scores[idx] for idx in top_ppcs]
      # Need to round, otherwise floating point precision issues will result
      # in values slightly above 1
      avg = np.round(
          np.sqrt(
              np.average(
                  np.power(palette_rgb[color_ids] * rgb_max, 2),
                  axis=0,
                  weights=weights)) / rgb_max, 4)
      if (avg > 1).sum() > 0:
        print(avg)
      color = avg
    rgb_vals.append(list(color))
    hex_vals.append("#%02x%02x%02x" %
                    tuple(np.array(color * rgb_max, dtype=int)))
  rgb_vals = np.array(rgb_vals)

  # Create t-SNE model
  tsne_model = TSNE(
      perplexity=30,
      n_components=2,
      n_iter=1000,
      random_state=23,
      learning_rate=500,
      init="pca")
  new_values = tsne_model.fit_transform(ppc_scores)
  x = []
  y = []
  for value in new_values:
    x.append(value[0])
    y.append(value[1])
  # Put data in dataframe
  df = pd.DataFrame({
      "x": x,
      "y": y,
      "color": hex_vals,
      "label(s)": top_categories,
      "text": texts
  })

  df = df[df["label(s)"] != "other"]
  df["top_label"] = df["label(s)"].str.split(",").str[0]

  # Two selections:
  # - a brush that is active on the top panel
  # - a multi-click that is active on the bottom panel
  brush = alt.selection(type="interval")
  click = alt.selection_multi(encodings=["color"])

  sample = df.sample(5000)  # max 5000 examples can be plotted
  points = alt.Chart(sample).mark_point(
      filled=True, size=50).encode(
          x="x:Q",
          y="y:Q",
          color=alt.Color("color", scale=None),
          tooltip=["label(s)", "text"]).properties(
              width=700, height=600).add_selection(brush)

  # Bottom panel is a bar chart
  bars = alt.Chart(sample).mark_bar().encode(
      x="count()",
      y="top_label:N",
      color=alt.condition(click, alt.Color("color:N", scale=None),
                          alt.value("lightgray")),
  ).transform_filter(brush.ref()).properties(
      width=700, selection=click)

  chart = alt.vconcat(
      points, bars, data=sample, title="t-SNE Projection of Examples")

  chart.save(FLAGS.plot_dir + "/tsne.html", format="html")
