# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_1/remove_label_tree.py#L12-L32
# smelly line(s) in the original file: 17
# smelly line(s) in this file: 12
# ids: codesmile_0062
def main(args):
    lostconfig = config.LOSTConfig()
    dbm = access.DBMan(lostconfig)
    if args.csv_file is not None:
        df = pd.read_csv(args.csv_file)
        name = df[df['parent_leaf_id'].isnull()]['name'].values[0]
    elif args.name is not None:
        name = args.name
    else:
        logging.error("Either a *csv_file* or a *name* for a label tree needs to be provided!")
        return
    root_leaf = next(filter(lambda x: x.name==name, dbm.get_all_label_trees()),None)
    if root_leaf is None:
        logging.warning('LabelTree not present in database! {}'.format(args.csv_file))
    else:
        try:
            LabelTree(dbm, root_leaf=root_leaf, logger=logging).delete_tree()
            logging.info('Deleted tree with name: {}'.format(name))
        except:
            logging.error('Can not delete label tree. One of the labels is used by a pipeline!')
    dbm.close_session()
