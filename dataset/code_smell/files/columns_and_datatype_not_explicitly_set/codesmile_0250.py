# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_92/visualize.py#L3-L44
# smelly line(s) in the original file: 18
# smelly line(s) in this file: 22
# ids: codesmile_0250
def datahtml(
    bucket_name,
    commit_sha,
    train_file_path
):
    import json
    import seaborn as sns
    import matplotlib.pyplot as plt
    import os
    image_path = os.path.join(bucket_name, commit_sha, 'visualization.png')
    image_url = os.path.join('https://storage.googleapis.com', bucket_name.lstrip('gs://'), commit_sha, 'visualization.png')
    html_path = os.path.join(bucket_name, 'kaggle.html')
    # ouptut visualization to a file

    import pandas as pd
    df_train = pd.read_csv(train_file_path)
    sns.set()
    cols = ['SalePrice', 'OverallQual', 'GrLivArea', 'GarageCars', 'TotalBsmtSF', 'FullBath', 'YearBuilt']
    sns.pairplot(df_train[cols], size = 3)
    plt.savefig('visualization.png')
    from tensorflow.python.lib.io import file_io
    file_io.copy('visualization.png', image_path)
    rendered_template = """
    <html>
        <head>
            <title>correlation image</title>
        </head>
        <body>
            <img src={}>
        </body>
    </html>""".format(image_url)
    file_io.write_string_to_file(html_path, rendered_template)

    metadata = {
        'outputs' : [{
        'type': 'web-app',
        'storage': 'gcs',
        'source': html_path,
        }]
    }
    with file_io.FileIO('/mlpipeline-ui-metadata.json', 'w') as f:
        json.dump(metadata, f)
