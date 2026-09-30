# smell: Matrix Multiplication API Misused (R12)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_22/ppca.py#L108-L115
# smelly line(s) in the original file: 113, 114
# smelly line(s) in this file: 12, 13
# ids: codesmile_0023, codesmile_0024
def PartialCorr(x, y, covar):
  """Calculate partial correlation."""
  cvar = np.atleast_2d(covar)
  beta_x = np.linalg.lstsq(cvar, x, rcond=None)[0]
  beta_y = np.linalg.lstsq(cvar, y, rcond=None)[0]
  res_x = x - np.dot(cvar, beta_x)
  res_y = y - np.dot(cvar, beta_y)
  return spearmanr(res_x, res_y)
