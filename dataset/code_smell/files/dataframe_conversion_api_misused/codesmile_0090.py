# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_17/ukb.py#L227-L284
# smelly line(s) in the original file: 262, 263, 264, 265, 275
# smelly line(s) in this file: 42, 43, 44, 45, 55
# ids: codesmile_0090, codesmile_0091, codesmile_0092, codesmile_0093, codesmile_0094
def simulating_y_from_clinical(
    clinical_sim,
    var = 'creatinine',
    simulate_y = False,
    rep = 30):
  """Simulate the outcome Y from clinical or mu(x,t).

  Args:
    clinical_sim: pd.DataFrame with simulated pi() and mu(). Colnames: 'eid',
    'image_id', 'sim_0_pi','sim_0_mu0','sim_0_mu1',
       ...
    'sim_b_pi','sim_b_mu0','sim_b_mu1', clinical variables (optional)
    var: which variable from clinical data will be used as outcome.
    simulate_y: use mu(x,t) instead of var.
    rep: number of repetitions.
  Returns:
    clinical_sim: pd.DataFrame, keys: 'eid', 'image_id',
      'sim_0_pi','sim_0_mu0','sim_0_mu1',
       ...
      'sim_b_pi','sim_b_mu0','sim_b_mu1', clinical variables (optional),
      'sim_0_y', ..., 'sim_b_pi' (new columns)
    true_treatment_effect: np.array, length b (one value per repetition b).
  """
  scaler = MinMaxScaler((0, 100))
  true_treatment_effect = []

  for b in range(rep):
    y_name = f'sim_{b}_y'
    t_name = f'sim_{b}_pi'
    mu1_name = f'sim_{b}_mu1'
    mu0_name = f'sim_{b}_mu0'
    t = clinical_sim[t_name]
    t = t == 1

    if simulate_y:
      mu0 = copy.deepcopy(clinical_sim[mu0_name].values.reshape(-1, 1))
      mu1 = copy.deepcopy(clinical_sim[mu1_name].values.reshape(-1, 1))
      y = clinical_sim['sim_' + str(b) + '_mu0'].values
      y[t] = clinical_sim['sim_' + str(b) + '_mu1'].values[t]
      y = scaler.fit_transform(y.reshape(-1, 1))
      mu0 = scaler.transform(mu0)
      mu1 = scaler.transform(mu1)
      dif = mu0 - mu1
      true_treatment_effect.append(dif.mean())
      y = y.ravel()
    else:
      clinical_sim = clinical_sim.dropna(subset=[var])
      clinical_sim.reset_index(inplace=True, drop=True)
      y_ = scaler.fit_transform(clinical_sim[var].values.reshape(-1, 1))
      np.random.seed(b)
      tau = np.random.uniform(0, 5, 1)[0]
      y = [
          y_[i][0] + tau if t[i] else y_[i][0]
          for i in range(clinical_sim.shape[0])
      ]
      true_treatment_effect.append(tau)
    clinical_sim[y_name] = y
  return clinical_sim, true_treatment_effect
