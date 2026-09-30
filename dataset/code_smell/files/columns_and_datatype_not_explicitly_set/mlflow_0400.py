# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/mlflow/recipes/steps/transform.py#L94-L164
# smelly line(s) in the original file: 104, 112
# smelly line(s) in this file: 17, 25
# ids: mlflow_0400, mlflow_0401
def _run(self, output_directory):
    import pandas as pd

    run_start_time = time.time()

    train_data_path = get_step_output_path(
        recipe_root_path=self.recipe_root,
        step_name="split",
        relative_path="train.parquet",
    )
    train_df = pd.read_parquet(train_data_path)
    validate_classification_config(self.task, self.positive_class, train_df, self.target_col)

    validation_data_path = get_step_output_path(
        recipe_root_path=self.recipe_root,
        step_name="split",
        relative_path="validation.parquet",
    )
    validation_df = pd.read_parquet(validation_data_path)

    sys.path.append(self.recipe_root)

    def get_identity_transformer():
        from sklearn.pipeline import Pipeline
        from sklearn.preprocessing import FunctionTransformer

        return Pipeline(steps=[("identity", FunctionTransformer())])

    if "transformer_method" not in self.step_config and self.step_config["using"] == "custom":
        raise MlflowException(
            "Missing 'transformer_method' configuration in the transform step, "
            "which is using 'custom'.",
            error_code=INVALID_PARAMETER_VALUE,
        )
    method_config = self.step_config.get("transformer_method")
    transformer = None
    if method_config and self.step_config["using"] == "custom":
        transformer_fn = getattr(
            importlib.import_module(_USER_DEFINED_TRANSFORM_STEP_MODULE), method_config
        )
        transformer = _validate_user_code_output(transformer_fn)
    transformer = transformer if transformer else get_identity_transformer()
    transformer.fit(train_df.drop(columns=[self.target_col]), train_df[self.target_col])

    def transform_dataset(dataset):
        features = dataset.drop(columns=[self.target_col])
        transformed_features = transformer.transform(features)
        if not isinstance(transformed_features, pd.DataFrame):
            num_features = transformed_features.shape[1]
            columns = _get_output_feature_names(transformer, num_features, features.columns)
            transformed_features = pd.DataFrame(transformed_features, columns=columns)
        transformed_features[self.target_col] = dataset[self.target_col].values
        return transformed_features

    train_transformed = transform_dataset(train_df)
    validation_transformed = transform_dataset(validation_df)

    with open(os.path.join(output_directory, "transformer.pkl"), "wb") as f:
        cloudpickle.dump(transformer, f)

    train_transformed.to_parquet(
        os.path.join(output_directory, "transformed_training_data.parquet")
    )
    validation_transformed.to_parquet(
        os.path.join(output_directory, "transformed_validation_data.parquet")
    )

    self.run_end_time = time.time()
    self.execution_duration = self.run_end_time - run_start_time

    return self._build_profiles_and_card(train_df, train_transformed, transformer)
