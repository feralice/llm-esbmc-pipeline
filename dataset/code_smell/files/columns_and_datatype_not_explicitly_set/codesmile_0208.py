# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_11/converter.py#L31-L36
# smelly line(s) in the original file: 32, 33, 34
# smelly line(s) in this file: 8, 9, 10
# ids: codesmile_0208, codesmile_0209, codesmile_0210
def csv_to_h5ad(csv_prefix):
  count = pd.read_csv(f'{csv_prefix}.counts.csv', index_col=0)
  metadata = pd.read_csv(f'{csv_prefix}.metadata.csv', index_col=0)
  featuredata = pd.read_csv(f'{csv_prefix}.featuredata.csv', index_col=0)
  adata = anndata.AnnData(X=count.transpose(), obs=metadata, var=featuredata)
  adata.write(f'{csv_prefix}.h5ad')
