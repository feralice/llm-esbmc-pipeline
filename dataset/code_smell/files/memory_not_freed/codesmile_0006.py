# smell: Memory Not Freed (R10)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_46/polblogs_experiment.py#L431-L485
# smelly line(s) in the original file: 453
# smelly line(s) in this file: 29
# ids: codesmile_0006
def scores(X,
           y,
           random_state=12345,
           scoring='accuracy',
           training_ratios=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9],
           C_log_lims=[-6, 6],
           gamma_log_lims=[-6, 6],
           cv=5,
           n_jobs=64):
  # Set up training & scoring
  n = X.shape[0]
  svm_scores = {
      'linear': [0.0] * len(training_ratios),
      'rbf': [0.0] * len(training_ratios)
  }
  gamma_range = numpy.logspace(-6, 1, 6)
  C_range = numpy.logspace(C_log_lims[0], 1, C_log_lims[1])
  gamma_range = numpy.logspace(gamma_log_lims[0], 1, gamma_log_lims[1])
  lin_pipe = Pipeline([('scale', StandardScaler()), ('clf', LinearSVC())])
  lin_param_grid = dict(clf__C=C_range)
  rbf_pipe = Pipeline([('scale', StandardScaler()), ('clf', SVC())])
  rbf_param_grid = dict(clf__C=C_range, clf__gamma=gamma_range)
  for j, r in enumerate(training_ratios):
    print('--training ratio %0.3f' % r)
    # Choose training set
    numpy.random.seed(random_state + j)
    train_set = numpy.random.randint(low=0, high=n, size=int(r * n))
    train_set_set = set(train_set)
    X_train = X[train_set]
    y_train = y[train_set]
    X_test = numpy.array([v for i, v in enumerate(X) if i not in train_set_set])
    y_test = numpy.array([v for i, v in enumerate(y) if i not in train_set_set])
    print('----lin')
    # Fit and score Linear SVM
    lin_grid = GridSearchCV(
        lin_pipe,
        param_grid=lin_param_grid,
        cv=cv,
        n_jobs=n_jobs,
        verbose=1,
        scoring=scoring)
    lin_grid.fit(X_train, y_train)
    svm_scores['linear'][j] = lin_grid.score(X_test, y_test)
    print('----rbf')
    # Fit and score RBF SVM
    rbf_grid = GridSearchCV(
        rbf_pipe,
        param_grid=rbf_param_grid,
        cv=cv,
        n_jobs=n_jobs,
        verbose=1,
        scoring=scoring)
    rbf_grid.fit(X_train, y_train)
    svm_scores['rbf'][j] = rbf_grid.score(X_test, y_test)
  return svm_scores
