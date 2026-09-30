# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/pyfunc/test_scoring_server.py#L434-L437
# smelly line(s) in the original file: 436
# smelly line(s) in this file: 9
# ids: mlflow_0307
def _shuffle_pdf(pdf):
    cols = list(pdf.columns)
    random.shuffle(cols)
    return pdf[cols]
