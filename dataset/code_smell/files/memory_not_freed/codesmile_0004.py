# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_46/polblogs_experiment.py#L285-L309
# smelly line(s) in the original file: 296
# smelly line(s) in this file: 18
# ids: codesmile_0004
def score_results(weights,
                  labels,
                  num_fits=30,
                  training_ratios=numpy.arange(0.01, 0.10, 0.01),
                  max_iter=1000,
                  scale_columns=True):
  n = weights.shape[0]
  if scale_columns:
    weights = scale(weights, with_mean=False, axis=0)
  macro_scores = dict(zip(training_ratios, [0.0] * len(training_ratios)))
  micro_scores = dict(zip(training_ratios, [0.0] * len(training_ratios)))
  for r in training_ratios:
    macros = 0.0
    micros = 0.0
    for _ in range(num_fits):
      training_sample = numpy.random.choice(list(range(n)), int(n * r))
      multi_linsvm = OneVsRestClassifier(LinearSVC(max_iter=max_iter))
      multi_linsvm.fit(weights[training_sample], labels[training_sample])
      macros += f1_score(
          labels, multi_linsvm.predict(weights), average='macro') / num_fits
      micros += f1_score(
          labels, multi_linsvm.predict(weights), average='micro') / num_fits
    macro_scores[r] = macros
    micro_scores[r] = micros
  return macro_scores, micro_scores
