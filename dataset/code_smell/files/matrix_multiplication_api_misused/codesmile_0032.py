# smell: Matrix Multiplication API Misused (R12)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_41/plotting.py#L187-L207
# smelly line(s) in the original file: 200
# smelly line(s) in this file: 20
# ids: codesmile_0032
def make_comparison_gmm_datasets():
  onp.random.seed(0)

  n_samples = 1500
  _ = datasets.make_circles(n_samples=n_samples, factor=.5, noise=.05)
  _ = datasets.make_moons(n_samples=n_samples, noise=.05)
  blobs = datasets.make_blobs(n_samples=n_samples, random_state=8)
  no_structure = onp.random.rand(n_samples, 2), None

  # Anisotropicly distributed data
  random_state = 170
  X, y = datasets.make_blobs(n_samples=n_samples, random_state=random_state)
  transformation = [[0.6, -0.6], [-0.4, 0.8]]
  X_aniso = onp.dot(X, transformation)
  aniso = (X_aniso, y)

  # blobs with varied variances
  varied = datasets.make_blobs(n_samples=n_samples,
                               cluster_std=[1.0, 2.5, 0.5],
                               random_state=random_state)
  return varied, aniso, blobs, no_structure
