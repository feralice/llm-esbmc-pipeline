# smell: Chain Indexing (R20)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_5/evaluate.py#L14-L30
# smelly line(s) in the original file: 25
# smelly line(s) in this file: 18
# ids: codesmile_0165
def __init__(self, name):
    self.name = name

    meta_info = pd.read_csv(os.path.join(os.path.dirname(__file__), 'master.csv'), index_col=0, keep_default_na=False)
    if not self.name in meta_info:
        print(self.name)
        error_mssg = 'Invalid dataset name {}.\n'.format(self.name)
        error_mssg += 'Available datasets are as follows:\n'
        error_mssg += '\n'.join(meta_info.keys())
        raise ValueError(error_mssg)

    self.eval_metric = meta_info[self.name]['eval metric']

    if 'hits@' in self.eval_metric:
        ### Hits@K

        self.K = int(self.eval_metric.split('@')[1])
