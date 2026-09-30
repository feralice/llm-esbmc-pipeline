# smell: Columns and DataType Not Explicitly Set (R21)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/4/files/EvalID_51/script_download_data.py#L338-L389
# smelly line(s) in the original file: 357, 358, 367, 368
# smelly line(s) in this file: 26, 27, 36, 37
# ids: codesmile_0237, codesmile_0238, codesmile_0239, codesmile_0240
def download_m5(data_folder):
    """Processes M5 Kaggle competition dataset.

    Raw files can be manually downloaded from Kaggle (without test set) @
      https://www.kaggle.com/c/m5-forecasting-accuracy/data

    Data is downloaded from Google Drive from organizers @
      https://github.com/Mcompetitions/M5-methods

    Args:
      config: Default experiment config for M5
    """
    required_files = ['sales_train_evaluation.csv', 'sales_test_evaluation.csv', 
                      'sell_prices.csv', 'calendar.csv', 'weights_validation.csv', 
                      'weights_evaluation.csv']

    for file in required_files:
        assert os.path.exists(os.path.join(data_folder, file)), "There are files missing from the data_folder. Please download following files from https://github.com/Mcompetitions/M5-methods"

    core_frame = pd.read_csv(os.path.join(data_folder, "sales_train_evaluation.csv"))
    test_frame = pd.read_csv(os.path.join(data_folder, "sales_test_evaluation.csv"))
    # Add 28 prediction values for final model evaluation
    core_frame = core_frame.merge(test_frame, on=['item_id', 'dept_id', 'cat_id', 'store_id', 'state_id'])
    del test_frame

    id_vars = ["id", "item_id", "dept_id", "cat_id", "store_id", "state_id"]
    ts_cols = [col for col in core_frame.columns if col not in id_vars]

    core_frame['id'] = core_frame.item_id + '_' + core_frame.store_id
    prices = pd.read_csv(os.path.join(data_folder, "sell_prices.csv"))
    calendar = pd.read_csv(os.path.join(data_folder, "calendar.csv"))

    calendar = calendar.sort_values('date')
    calendar['d'] = [f'd_{i}' for i in range(1, calendar.shape[0]+1)]

    core_frame = core_frame.melt(
        id_vars,
        value_vars=ts_cols,
        var_name='d',
        value_name='items_sold'
    )
    core_frame = core_frame.merge(calendar, left_on="d", right_on='d')
    core_frame = core_frame.merge(prices, on=['store_id', 'item_id', 'wm_yr_wk'], how='outer')

    # According to M5-Comperition-Guide-Final-10-March-2020:
    # if not available, this means that the product was not sold during the examined week.
    core_frame.sell_price.fillna(-1, inplace=True)

    core_frame['weight'] = 1.0
    core_frame.loc[core_frame.sell_price == -1, 'weight'] = 0

    core_frame.to_csv(os.path.join(data_folder, "M5.csv"))
