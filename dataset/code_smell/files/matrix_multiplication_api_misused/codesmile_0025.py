# smell: Matrix Multiplication API Misused (R12)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_22/ppca.py#L118-L135
# smelly line(s) in the original file: 125, 127, 130, 131, 135
# smelly line(s) in this file: 14, 16, 19, 20, 24
# ids: codesmile_0025, codesmile_0026, codesmile_0027, codesmile_0028, codesmile_0029
def Varimax(phi, gamma=1, q=20, tol=1e-6):
  """Source: https://stackoverflow.com/questions/17628589/perform-varimax-rotation-in-python-using-numpy."""
  p, k = phi.shape
  r = np.eye(k)
  d = 0
  for _ in range(q):
    d_old = d
    l = np.dot(phi, r)
    u, s, vh = LA.svd(
        np.dot(
            phi.T,
            np.asarray(l)**3 -
            (gamma / p) * np.dot(l, np.diag(np.diag(np.dot(l.T, l))))))
    r = np.dot(u, vh)
    d = np.sum(s)
    if d / d_old < tol:
      break
  return np.dot(phi, r)
