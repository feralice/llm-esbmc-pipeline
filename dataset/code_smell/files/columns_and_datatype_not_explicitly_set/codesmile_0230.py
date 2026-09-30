# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/3/files/EvalID_40/stgat_data.py#L143-L167
# smelly line(s) in the original file: 145, 146
# smelly line(s) in this file: 9, 10
# ids: codesmile_0230, codesmile_0231
def read_stgat_data(folder, num_nodes):
    device = torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu")
    W = pd.read_csv(osp.join(folder, "W_{}.csv".format(num_nodes)))
    T_V = pd.read_csv(osp.join(folder, "V_{}.csv".format(num_nodes)))
    V = T_V.drop('timestamp',axis=1)
    num_samples, num_nodes = V.shape
    scaler = StandardScaler()


    # format graph for pyg layer inputs
    G = sp.coo_matrix(W)
    edge_index = torch.tensor(np.array([G.row, G.col]), dtype=torch.int64).to(device)
    edge_weight = torch.tensor(G.data).float().to(device)
    data = Graph()
    data.num_nodes = num_nodes
    data.num_samples = num_samples
    data.edge_index = edge_index
    data.edge_weight = edge_weight
    data.scaler = scaler
    data.V = V
    data.W = W
    data.timestamp = T_V['timestamp']
    data.node_ids = V.columns

    return data
