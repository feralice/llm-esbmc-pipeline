# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_60/utils.py#L88-L118
# smelly line(s) in the original file: 97, 109
# smelly line(s) in this file: 16, 28
# ids: codesmile_0065, codesmile_0066
def generate_metadata(train_images_dir, test_images_dir, depths_filepath):
    depths = pd.read_csv(depths_filepath)
    salt_exists_dict = get_salt_existence()

    metadata = {}
    for filename in tqdm(os.listdir(os.path.join(train_images_dir, 'images'))):
        image_filepath = os.path.join(train_images_dir, 'images', filename)
        mask_filepath = os.path.join(train_images_dir, 'masks', filename)
        image_id = filename.split('.')[0]
        depth = depths[depths['id'] == image_id]['z'].values[0]

        metadata.setdefault('file_path_image', []).append(image_filepath)
        metadata.setdefault('file_path_mask', []).append(mask_filepath)
        metadata.setdefault('is_train', []).append(1)
        metadata.setdefault('id', []).append(image_id)
        metadata.setdefault('z', []).append(depth)
        metadata.setdefault('salt_exists', []).append(salt_exists_dict[image_id])

    for filename in tqdm(os.listdir(os.path.join(test_images_dir, 'images'))):
        image_filepath = os.path.join(test_images_dir, 'images', filename)
        image_id = filename.split('.')[0]
        depth = depths[depths['id'] == image_id]['z'].values[0]

        metadata.setdefault('file_path_image', []).append(image_filepath)
        metadata.setdefault('file_path_mask', []).append(None)
        metadata.setdefault('is_train', []).append(0)
        metadata.setdefault('id', []).append(image_id)
        metadata.setdefault('z', []).append(depth)
        metadata.setdefault('salt_exists', []).append(0)

    return pd.DataFrame(metadata)
