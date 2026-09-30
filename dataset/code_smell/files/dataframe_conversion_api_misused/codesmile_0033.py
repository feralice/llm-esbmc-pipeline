# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_19/predictor.py#L62-L91
# smelly line(s) in the original file: 82
# smelly line(s) in this file: 27
# ids: codesmile_0033
def transformation():
    """Do an inference on a single batch of data. In this sample server, we take data as CSV, convert
    it to a pandas data frame for internal use and then convert the predictions back to CSV (which really
    just means one prediction per line, since there's a single column.
    """
    data = None

    # Convert from CSV to pandas
    if flask.request.content_type == "text/csv":
        data = flask.request.data.decode("utf-8")
        s = StringIO(data)
        data = pd.read_csv(s, header=None)
    else:
        return flask.Response(
            response="This predictor only supports CSV data", status=415, mimetype="text/plain"
        )

    print("Invoked with {} records".format(data.shape[0]))

    # Do the prediction
    predictions = ScoringService.predict(data.values)

    # Convert from numpy back to CSV
    out = StringIO()
    pd.DataFrame({"results": predictions}).to_csv(out, header=False, index=False)
    result = out.getvalue().rstrip(
        "\n"
    )  # this is essential for Model Monitoring to work correctly.

    return flask.Response(response=result, status=200, mimetype="text/csv")
