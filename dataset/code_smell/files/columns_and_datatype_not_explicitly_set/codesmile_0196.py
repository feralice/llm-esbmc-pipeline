# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_81/dataset.py#L61-L125
# smelly line(s) in the original file: 115, 122
# smelly line(s) in this file: 61, 68
# ids: codesmile_0196, codesmile_0197
def pre_process(self):
    processed_dir = osp.join(self.root, 'processed')
    raw_dir = osp.join(self.root, 'raw')
    pre_processed_file_path = osp.join(processed_dir, 'data_processed')

    if os.path.exists(pre_processed_file_path):
        loaded_dict = torch.load(pre_processed_file_path, 'rb')
        self.graphs, self.labels = loaded_dict['graphs'], loaded_dict['labels']

    else:
        ### check download
        if self.binary:
            # npz format
            has_necessary_file = osp.exists(osp.join(self.root, 'raw', 'data.npz'))
        else:
            # csv file
            has_necessary_file = osp.exists(osp.join(self.root, 'raw', 'edge.csv.gz'))

        ### download
        if not has_necessary_file:
            url = self.meta_info['url']
            if decide_download(url):
                path = download_url(url, self.original_root)
                extract_zip(path, self.original_root)
                os.unlink(path)
                # delete folder if there exists
                try:
                    shutil.rmtree(self.root)
                except:
                    pass
                shutil.move(osp.join(self.original_root, self.download_name), self.root)
            else:
                print('Stop download.')
                exit(-1)

        ### preprocess
        add_inverse_edge = self.meta_info['add_inverse_edge'] == 'True'

        if self.meta_info['additional node files'] == 'None':
            additional_node_files = []
        else:
            additional_node_files = self.meta_info['additional node files'].split(',')

        if self.meta_info['additional edge files'] == 'None':
            additional_edge_files = []
        else:
            additional_edge_files = self.meta_info['additional edge files'].split(',')

        if self.binary:
            self.graphs = read_binary_graph_raw(raw_dir, add_inverse_edge = add_inverse_edge)
        else:
            self.graphs = read_csv_graph_raw(raw_dir, add_inverse_edge = add_inverse_edge, additional_node_files = additional_node_files, additional_edge_files = additional_edge_files)

        if self.task_type == 'subtoken prediction':
            labels_joined = pd.read_csv(osp.join(raw_dir, 'graph-label.csv.gz'), compression='gzip', header = None).values
            # need to split each element into subtokens
            self.labels = [str(labels_joined[i][0]).split(' ') for i in range(len(labels_joined))]
        else:
            if self.binary:
                self.labels = np.load(osp.join(raw_dir, 'graph-label.npz'))['graph_label']
            else:
                self.labels = pd.read_csv(osp.join(raw_dir, 'graph-label.csv.gz'), compression='gzip', header = None).values

        print('Saving...')
        torch.save({'graphs': self.graphs, 'labels': self.labels}, pre_processed_file_path, pickle_protocol=4)
