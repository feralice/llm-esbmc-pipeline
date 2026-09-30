# smell: Matrix Multiplication API Misused (R12)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_32/recom_amr.py#L263-L289
# smelly line(s) in the original file: 287, 288
# smelly line(s) in this file: 31, 32
# ids: codesmile_0030, codesmile_0031
def score(self, user_idx, item_idx=None):
    """Predict the scores/ratings of a user for an item.

    Parameters
    ----------
    user_idx: int, required
        The index of the user for whom to perform score prediction.

    item_idx: int, optional, default: None
        The index of the item for which to perform score prediction.
        If None, scores for all known items will be returned.

    Returns
    -------
    res : A scalar or a Numpy array
        Relative scores that the user gives to the item or to all known items

    """
    if item_idx is None:
        known_item_scores = np.zeros(self.gamma_item.shape[0], dtype=np.float32)
        fast_dot(self.gamma_user[user_idx], self.gamma_item, known_item_scores)
        fast_dot(self.gamma_user[user_idx], self.theta_item, known_item_scores)
        return known_item_scores
    else:
        item_score = np.dot(self.gamma_item[item_idx], self.gamma_user[user_idx])
        item_score += np.dot(self.theta_item[item_idx], self.gamma_user[user_idx])
        return item_score
