# smell: NaN Equivalence Comparison Misused (R18)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_58/sklearn.py#L126-L133
# smelly line(s) in the original file: 129
# smelly line(s) in this file: 10
# ids: codesmile_0147
def get_params(self, deep=False):
    """Get parameter.s"""
    params = super(XGBModel, self).get_params(deep=deep)
    if params['missing'] is np.nan:
        params['missing'] = None  # sklearn doesn't handle nan. see #4725
    if not params.get('eval_metric', True):
        del params['eval_metric']  # don't give as None param to Booster
    return params
