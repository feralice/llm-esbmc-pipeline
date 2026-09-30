# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_81/dataset.py#L10-L59
# smelly line(s) in the original file: 26
# smelly line(s) in this file: 23
# ids: codesmile_0195
def __init__(self, name, root = 'dataset', meta_dict = None):
    '''
        - name (str): name of the dataset
        - root (str): root directory to store the dataset folder

        - meta_dict: dictionary that stores all the meta-information about data. Default is None, 
                but when something is passed, it uses its information. Useful for debugging for external contributers.
    '''

    self.name = name ## original name, e.g., ogbg-hib

    if meta_dict is None:
        self.dir_name = '_'.join(name.split('-')) ## replace hyphen with underline, e.g., ogbg_hiv
        self.original_root = root
        self.root = osp.join(root, self.dir_name)

        master = pd.read_csv(os.path.join(os.path.dirname(__file__), 'master.csv'), index_col=0, keep_default_na=False)
        if not self.name in master:
            error_mssg = 'Invalid dataset name {}.\n'.format(self.name)
            error_mssg += 'Available datasets are as follows:\n'
            error_mssg += '\n'.join(master.keys())
            raise ValueError(error_mssg)
        self.meta_info = master[self.name]

    else:
        self.dir_name = meta_dict['dir_path']
        self.original_root = ''
        self.root = meta_dict['dir_path']
        self.meta_info = meta_dict

    # check version
    # First check whether the dataset has been already downloaded or not.
    # If so, check whether the dataset version is the newest or not.
    # If the dataset is not the newest version, notify this to the user. 
    if osp.isdir(self.root) and (not osp.exists(osp.join(self.root, 'RELEASE_v' + str(self.meta_info['version']) + '.txt'))):
        print(self.name + ' has been updated.')
        if input('Will you update the dataset now? (y/N)\n').lower() == 'y':
            shutil.rmtree(self.root)

    self.download_name = self.meta_info['download_name'] ## name of downloaded file, e.g., tox21

    self.num_tasks = int(self.meta_info['num tasks'])
    self.eval_metric = self.meta_info['eval metric']
    self.task_type = self.meta_info['task type']
    self.num_classes = self.meta_info['num classes']
    self.binary = self.meta_info['binary'] == 'True'

    super(GraphPropPredDataset, self).__init__()

    self.pre_process()
