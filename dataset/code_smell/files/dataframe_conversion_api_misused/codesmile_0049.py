# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_17/ukb.py#L577-L655
# smelly line(s) in the original file: 648, 649
# smelly line(s) in this file: 78, 79
# ids: codesmile_0049, codesmile_0050
def generate_simulations(path,
                         b = 30,
                         hx_name = 'hx.csv',
                         output_name = 'sim_seeds.csv',
                         extract_id = True,
                         load_features = False,
                         features = None):
  """Generate the p(x) and mu(x,y) from h(x).

  Args:
    path: path for the hx.csv file.
    b: repetitions
    hx_name: features extracted name.
    output_name: new file name.
    extract_id: for the UK Biobank we need to extract ID from url.
    load_features: read features from path.
    features: pass features pd.DataFrame as argument.
  """
  def _eid_from_image_id(image_id):
    """Parses an `image_id` and returns the corresponding eid."""
    eid = image_id.split('/')[-1]
    eid = eid.split('_')[0]
    try:
      eid = int(eid)
    except ValueError:
      raise ValueError('Image ID did not match our transformation')
    return str(eid)

  def _generation_weights(n_cols = 2048,
                          seed = 0):
    np.random.seed(seed)
    gam = np.random.uniform(-1, 1, n_cols)
    eta1 = np.random.uniform(2, 3, n_cols)
    eta0 = np.random.uniform(1, 3, n_cols)
    return gam, eta1, eta0

  def _pi_x_function(features, gam):
    def sigmoid(x):
      return 1 / (1 + math.exp(-x))
    pi = np.matmul(features, gam)
    pi = pi.reshape(-1, 1)
    scaler = MinMaxScaler((-2, 2))
    pi = scaler.fit_transform(pi)
    pi = pi.ravel()
    pi = [sigmoid(item) for item in pi]
    np.random.seed(0)
    t = [np.random.binomial(1, item) for item in pi]
    return t

  def _mu_x_function(features, eta1, eta0):
    mu1 = np.array(np.matmul(features, eta1))
    mu0 = np.array(np.matmul(features, eta0))
    full = np.array(np.concatenate([mu1, mu0]))
    scaler = MinMaxScaler()
    scaler.fit(full.reshape(-1, 1))
    mu1 = scaler.transform(mu1.reshape(-1, 1))
    mu0 = scaler.transform(mu0.reshape(-1, 1))
    return mu1, mu0

  if load_features:
    with gfile.GFile(os.path.join(path, hx_name), mode='rt') as f:
      features = pd.read_csv(f)

  features_only = features.drop(['image_id'], axis=1)
  output = pd.DataFrame(features['image_id'])

  if extract_id:
    eid = [_eid_from_image_id(item) for item in features['image_id']]
    output['eid'] = eid
  for i in range(b):
    gam, eta1, eta0 = _generation_weights(features_only.shape[1], i)
    pi = _pi_x_function(features_only.values, gam)
    mu1, mu0 = _mu_x_function(features_only.values, eta1, eta0)
    output['sim_' + str(i) + '_pi'] = pi
    output['sim_' + str(i) + '_mu1'] = mu1
    output['sim_' + str(i) + '_mu0'] = mu0

  with gfile.GFile(os.path.join(path, output_name), 'wt') as out:
    out.write(output.to_csv(index=False))
