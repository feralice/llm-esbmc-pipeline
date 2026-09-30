# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_40/stgat_data.py#L32-L140
# smelly line(s) in the original file: 111, 115, 116
# smelly line(s) in this file: 86, 90, 91
# ids: codesmile_0069, codesmile_0070, codesmile_0071
def raw_data_processByNumNodes(raw_dir, num_nodes, meta_file_name):

    PeMS_daily = os.path.join(f'{raw_dir}', '*')
    PeMS_metadata = os.path.join(f'{raw_dir}', meta_file_name)
    output_dir = os.path.join(f'{raw_dir}')


    # Parameters
    outcome_var = 'avg_speed'
    files = glob.glob(PeMS_daily)
    files.remove(glob.glob(PeMS_metadata)[0])
    PeMS_columns = ['timestamp', 'station', 'district', 'freeway_num',
                    'direction_travel', 'lane_type', 'station_length',
                    'samples', 'perc_observed', 'total_flow', 'avg_occupancy',
                    'avg_speed']
    #PeMS_lane_columns = lambda x: ['lane_N_samples_{}'.format(x),
    #                               'lane_N_flow_{}'.format(x),
    #                               'lane_N_avg_occ_{}'.format(x),
    #                               'lane_N_avg_speed_{}'.format(x),
    #                               'lane_N_observed_{}'.format(x)]

    PeMS_all_columns = PeMS_columns.copy()
    for i in range(1, 9):
        PeMS_all_columns += PeMS_lane_columns(i)
    # Randomly select stations to build the dataset
    np.random.seed(42)
    station_file = files[0]
    station_file_content = pd.read_csv(station_file, header=0, names=PeMS_all_columns)
    station_file_content = station_file_content[PeMS_columns]
    station_file_content = station_file_content.dropna(subset=[outcome_var])
    unique_stations = station_file_content['station'].unique()
    selected_stations = np.random.choice(unique_stations, size=num_nodes, replace=False)

    # Build two-months of data for the selected stations/nodes
    station_data = pd.DataFrame({col: []} for col in PeMS_columns)
    for station_file in tqdm(files):
        # Get file date
        file_date_str = station_file.split(os.path.sep)[-1].split('.')[0]
        file_date = datetime(int(file_date_str.split('_')[-3]), int(file_date_str.split('_')[-2]),
                             int(file_date_str.split('_')[-1]))
        # Check if weekday
        if file_date.weekday() < 5:
            # Read CSV
            station_file_content = pd.read_csv(
                station_file, header=0, names=PeMS_all_columns)
            # Keep only columns of interest
            station_file_content = station_file_content[PeMS_columns]
            # Keep stations
            station_file_content = station_file_content[
                station_file_content['station'].isin(selected_stations)]
            # Append to dataset
            station_data = pd.concat([station_data, station_file_content])
    # Drop the 11 rows with missing values
    station_data = station_data.dropna(subset=['timestamp', outcome_var])
    station_data.head()
    station_data.shape
    station_metadata = pd.read_table(PeMS_metadata)
    station_metadata = station_metadata[['ID', 'Latitude', 'Longitude']]
    # Filter for selected stations
    station_metadata = station_metadata[station_metadata['ID'].isin(selected_stations)]
    station_metadata.head()
    # Keep only the required columns (time interval, station ID and the outcome variable)
    station_data = station_data[['timestamp', 'station', outcome_var]]
    station_data[outcome_var] = pd.to_numeric(station_data[outcome_var])
    # Reshape the dataset and aggregate the traffic speeds in each time interval
    V = station_data.pivot_table(index=['timestamp'], columns=['station'], values=outcome_var, aggfunc='mean')
    V.head()
    V.shape
    # Compute distances
    distances = pd.crosstab(station_metadata.ID, station_metadata.ID, normalize=True)
    distances_std = []
    for station_i in selected_stations:
        for station_j in selected_stations:
            if station_i == station_j:
                distances.at[station_j, station_i] = 0
            else:
                # Compute distance between stations
                station_i_meta = station_metadata[station_metadata['ID'] == station_i]
                station_j_meta = station_metadata[station_metadata['ID'] == station_j]
                if np.isnan(station_i_meta['Latitude'].values[0]) or np.isnan(station_i_meta['Longitude'].values[0]) or np.isnan(station_j_meta['Latitude'].values[0]) or np.isnan(station_j_meta['Longitude'].values[0]):
                    d_ij = 0
                else:
                    d_ij = geopy.distance.geodesic(
                        (station_i_meta['Latitude'].values[0], station_i_meta['Longitude'].values[0]),
                        (station_j_meta['Latitude'].values[0], station_j_meta['Longitude'].values[0])).m
                distances.at[station_j, station_i] = d_ij
                distances_std.append(d_ij)
    distances_std = np.std(distances_std)
    distances.head()
    W = pd.crosstab(station_metadata.ID, station_metadata.ID, normalize=True)
    epsilon = 0.1
    sigma = distances_std
    for station_i in selected_stations:
        for station_j in selected_stations:
            if station_i == station_j:
                W.at[station_j, station_i] = 0
            else:
                # Compute distance between stations
                d_ij = distances.loc[station_j, station_i]
                # Compute weight w_ij
                w_ij = np.exp(-d_ij ** 2 / sigma ** 2)
                if w_ij >= epsilon:
                    W.at[station_j, station_i] = w_ij
    W.head()
    # Save to file
    V = V.fillna(V.mean())
    V.to_csv(os.path.join(output_dir, 'V_{}.csv'.format(num_nodes)), index=True)
    W.to_csv(os.path.join(output_dir, 'W_{}.csv'.format(num_nodes)), index=False)
    station_metadata.to_csv(os.path.join(output_dir, 'station_meta_{}.csv'.format(num_nodes)), index=False)
