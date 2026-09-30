# smell: Randomness Uncontrolled (R2)
# validated by: SpecDetect4AI ground truth: 3 annotators, blind two-pass, consensus
# origin: https://github.com/PeterHamfelt/mlflow/blob/7a688bf4942c63608de91909aa4472ec1e6652b3/tests/store/tracking/test_file_store.py#L343-L426
# smelly line(s) in the original file: 382
# smelly line(s) in this file: 46
# ids: mlflow_0196
def _create_root(store):
    test_root = store.root_directory
    experiments = [str(random_int(100, int(1e9))) for _ in range(3)]
    exp_data = {}
    run_data = {}
    # Include default experiment
    experiments.append(FileStore.DEFAULT_EXPERIMENT_ID)
    default_exp_folder = os.path.join(test_root, str(FileStore.DEFAULT_EXPERIMENT_ID))
    if os.path.exists(default_exp_folder):
        shutil.rmtree(default_exp_folder)

    for exp in experiments:
        # create experiment
        exp_folder = os.path.join(test_root, str(exp))
        os.makedirs(exp_folder)
        current_time = get_current_time_millis()
        d = {
            "experiment_id": exp,
            "name": random_str(),
            "artifact_location": exp_folder,
            "lifecycle_stage": LifecycleStage.ACTIVE,
            "creation_time": current_time,
            "last_update_time": current_time,
        }
        exp_data[exp] = d
        write_yaml(exp_folder, FileStore.META_DATA_FILE_NAME, d)
        # add runs
        exp_data[exp]["runs"] = []
        for _ in range(2):
            run_id = uuid.uuid4().hex
            exp_data[exp]["runs"].append(run_id)
            run_folder = os.path.join(exp_folder, run_id)
            os.makedirs(run_folder)
            run_info = {
                "run_uuid": run_id,
                "run_id": run_id,
                "run_name": "name",
                "experiment_id": exp,
                "user_id": random_str(random_int(10, 25)),
                "status": random.choice(RunStatus.all_status()),
                "start_time": random_int(1, 10),
                "end_time": random_int(20, 30),
                "deleted_time": random_int(20, 30),
                "tags": [],
                "artifact_uri": os.path.join(run_folder, FileStore.ARTIFACTS_FOLDER_NAME),
                "lifecycle_stage": LifecycleStage.ACTIVE,
            }
            write_yaml(run_folder, FileStore.META_DATA_FILE_NAME, run_info)
            run_data[run_id] = run_info
            # tags
            os.makedirs(os.path.join(run_folder, FileStore.TAGS_FOLDER_NAME))
            # params
            params_folder = os.path.join(run_folder, FileStore.PARAMS_FOLDER_NAME)
            os.makedirs(params_folder)
            params = {}
            for _ in range(5):
                param_name = random_str(random_int(10, 12))
                param_value = random_str(random_int(10, 15))
                param_file = os.path.join(params_folder, param_name)
                with open(param_file, "w") as f:
                    f.write(param_value)
                params[param_name] = param_value
            run_data[run_id]["params"] = params
            # metrics
            metrics_folder = os.path.join(run_folder, FileStore.METRICS_FOLDER_NAME)
            os.makedirs(metrics_folder)
            metrics = {}
            for _ in range(3):
                metric_name = random_str(random_int(10, 12))
                timestamp = get_current_time_millis()
                metric_file = os.path.join(metrics_folder, metric_name)
                values = []
                for _ in range(10):
                    metric_value = random_int(100, 2000)
                    timestamp += random_int(10000, 2000000)
                    values.append((timestamp, metric_value))
                    with open(metric_file, "a") as f:
                        f.write("%d %d\n" % (timestamp, metric_value))
                metrics[metric_name] = values
            run_data[run_id]["metrics"] = metrics
            # artifacts
            os.makedirs(os.path.join(run_folder, FileStore.ARTIFACTS_FOLDER_NAME))

    return experiments, exp_data, run_data
