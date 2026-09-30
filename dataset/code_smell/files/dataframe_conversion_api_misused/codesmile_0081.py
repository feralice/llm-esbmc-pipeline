# smell: Dataframe Conversion API Misused (R14)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/1/files/EvalID_14/LinearGaussianCPD.py#L91-L161
# smelly line(s) in the original file: 127, 128, 133
# smelly line(s) in this file: 43, 44, 49
# ids: codesmile_0081, codesmile_0082, codesmile_0083
def maximum_likelihood_estimator(self, data, states):
    """
    Fit using MLE method.

    Parameters
    ----------
    data: pandas.DataFrame or 2D array
        Dataframe of values containing samples from the conditional distribution, (Y|X)
        and corresponding X values.

    states: All the input states that are jointly gaussian.

    Returns
    -------
    beta, variance (tuple): Returns estimated betas and the variance.
    """
    x_df = pd.DataFrame(data, columns=states)
    x_len = len(self.evidence)

    sym_coefs = []
    for i in range(0, x_len):
        sym_coefs.append("b" + str(i + 1) + "_coef")

    sum_x = x_df.sum()
    x = [sum_x["(Y|X)"]]
    coef_matrix = pd.DataFrame(columns=sym_coefs)

    # First we compute just the coefficients of beta_1 to beta_N.
    # Later we compute beta_0 and append it.
    for i in range(0, x_len):
        x.append(self.sum_of_product(x_df["(Y|X)"], x_df[self.evidence[i]]))
        for j in range(0, x_len):
            coef_matrix.loc[i, sym_coefs[j]] = self.sum_of_product(
                x_df[self.evidence[i]], x_df[self.evidence[j]]
            )

    coef_matrix.insert(0, "b0_coef", sum_x[self.evidence].values)
    row_1 = np.append([len(x_df)], sum_x[self.evidence].values)
    coef_matrix.loc[-1] = row_1
    coef_matrix.index = coef_matrix.index + 1  # shifting index
    coef_matrix.sort_index(inplace=True)

    beta_coef_matrix = np.matrix(coef_matrix.values, dtype="float")
    coef_inv = np.linalg.inv(beta_coef_matrix)
    beta_est = np.array(np.matmul(coef_inv, np.transpose(x)))
    self.beta = beta_est[0]

    sigma_est = 0
    x_len_df = len(x_df)
    for i in range(0, x_len):
        for j in range(0, x_len):
            sigma_est += (
                self.beta[i + 1]
                * self.beta[j + 1]
                * (
                    self.sum_of_product(
                        x_df[self.evidence[i]], x_df[self.evidence[j]]
                    )
                    / x_len_df
                    - np.mean(x_df[self.evidence[i]])
                    * np.mean(x_df[self.evidence[j]])
                )
            )

    sigma_est = np.sqrt(
        self.sum_of_product(x_df["(Y|X)"], x_df["(Y|X)"]) / x_len_df
        - np.mean(x_df["(Y|X)"]) * np.mean(x_df["(Y|X)"])
        - sigma_est
    )
    self.sigma_yx = sigma_est
    return self.beta, self.sigma_yx
