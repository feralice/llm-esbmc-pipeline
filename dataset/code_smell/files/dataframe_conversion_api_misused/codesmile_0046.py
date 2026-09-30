# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_21/transcode.py#L41-L130
# smelly line(s) in the original file: 118, 119, 120
# smelly line(s) in this file: 84, 85, 86
# ids: codesmile_0046, codesmile_0047, codesmile_0048
def main():
    args = parse_args()
    args_output = args.output
    args_input = args.input
    args_feature_spec_in = args.feature_spec_in
    args_feature_spec_out = args.feature_spec_out
    batch_size = args.chunk_size

    fspec_in_path = os.path.join(args_input, args_feature_spec_in)
    fspec_in = FeatureSpec.from_yaml(fspec_in_path)

    input_label_feature_name = fspec_in.channel_spec[LABEL_CHANNEL][0]
    input_numerical_features_list = fspec_in.channel_spec[NUMERICAL_CHANNEL]
    input_categorical_features_list = fspec_in.channel_spec[CATEGORICAL_CHANNEL]

    # Do a pass to establish the cardinalities: they influence the type we save the dataset as
    found_cardinalities = defaultdict(lambda: 0)
    for mapping_name, mapping in fspec_in.source_spec.items():
        df_iterators = []
        for chunk in mapping:
            assert chunk['type'] == 'csv', "Only csv files supported in this transcoder"
            assert len(chunk['files']) == 1, "Only one file per chunk supported in this transcoder"
            path_to_load = os.path.join(fspec_in.base_directory, chunk['files'][0])
            chunk_iterator = pd.read_csv(path_to_load, header=None, chunksize=batch_size, names=chunk['features'])
            df_iterators.append(chunk_iterator)

        zipped = zip(*df_iterators)
        for chunks in zipped:
            mapping_df = pd.concat(chunks, axis=1)
            for feature in input_categorical_features_list:
                mapping_cardinality = mapping_df[feature].max() + 1
                previous_cardinality = found_cardinalities[feature]
                found_cardinalities[feature] = max(previous_cardinality, mapping_cardinality)

    for feature in input_categorical_features_list:
        declared_cardinality = fspec_in.feature_spec[feature][CARDINALITY_SELECTOR]
        if declared_cardinality == 'auto':
            pass
        else:
            assert int(declared_cardinality) >= found_cardinalities[feature]
            found_cardinalities[feature] = int(declared_cardinality)

    categorical_cardinalities = [found_cardinalities[f] for f in input_categorical_features_list]
    number_of_numerical_features = fspec_in.get_number_of_numerical_features()

    fspec_out = FeatureSpec.get_default_feature_spec(number_of_numerical_features=number_of_numerical_features,
                                                     categorical_feature_cardinalities=categorical_cardinalities)
    fspec_out.base_directory = args.output

    for mapping_name, mapping in fspec_in.source_spec.items():

        # open files for outputting
        label_path, numerical_path, categorical_paths = fspec_out.get_mapping_paths(mapping_name)
        for path in [label_path, numerical_path, *categorical_paths.values()]:
            os.makedirs(os.path.dirname(path), exist_ok=True)
        output_categorical_features_list = fspec_out.get_categorical_feature_names()
        numerical_f = open(numerical_path, "ab+")
        label_f = open(label_path, "ab+")
        categorical_fs = [open(categorical_paths[name], "ab+") for name in output_categorical_features_list]
        categorical_feature_types = [get_categorical_feature_type(card) for card in categorical_cardinalities]

        df_iterators = []
        for chunk in mapping:
            # We checked earlier it's a single file chunk
            path_to_load = os.path.join(fspec_in.base_directory, chunk['files'][0])
            chunk_iterator = pd.read_csv(path_to_load, header=None, chunksize=batch_size, names=chunk['features'])
            df_iterators.append(chunk_iterator)

        zipped = zip(*df_iterators)
        for chunks in zipped:
            mapping_df = pd.concat(chunks, axis=1)  # This takes care of making sure feature names are unique

            # Choose the right columns
            numerical_df = mapping_df[input_numerical_features_list]
            categorical_df = mapping_df[input_categorical_features_list]
            label_df = mapping_df[[input_label_feature_name]]

            numerical = torch.tensor(numerical_df.values)
            label = torch.tensor(label_df.values)
            categorical = torch.tensor(categorical_df.values)

            # Append them to the binary files
            numerical_f.write(numerical.to(torch.float16).cpu().numpy().tobytes())
            label_f.write(label.to(torch.bool).cpu().numpy().tobytes())
            for cat_idx, cat_feature_type in enumerate(categorical_feature_types):
                categorical_fs[cat_idx].write(
                    categorical[:, cat_idx].cpu().numpy().astype(cat_feature_type).tobytes())

    feature_spec_save_path = os.path.join(args_output, args_feature_spec_out)
    fspec_out.to_yaml(output_path=feature_spec_save_path)
