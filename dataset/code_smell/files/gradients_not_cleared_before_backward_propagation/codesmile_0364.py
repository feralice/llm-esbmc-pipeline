# smell: Gradients Not Cleared Before Backward Propagation (R9)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_99/gp_models.py#L23-L185
# smelly line(s) in the original file: 80
# smelly line(s) in this file: 64
# ids: codesmile_0364
def main(args):
    # download and pre-process EEG data if not in test mode
    if not args.test:
        download_data()
        T_forecast = 349
        data = np.loadtxt("eeg.dat", delimiter=",", skiprows=19)
        print("[raw data shape] {}".format(data.shape))
        data = torch.tensor(data[::20, :-1]).double()
        print("[data shape after thinning] {}".format(data.shape))
    # in test mode (for continuous integration on github) so create fake data
    else:
        data = torch.randn(20, 3).double()
        T_forecast = 10

    T, obs_dim = data.shape
    T_train = T - T_forecast

    # standardize data
    data_mean = data[0:T_train, :].mean(0)
    data -= data_mean
    data_std = data[0:T_train, :].std(0)
    data /= data_std

    torch.manual_seed(args.seed)

    # set up model
    if args.model == "imgp":
        gp = IndependentMaternGP(
            nu=1.5, obs_dim=obs_dim, length_scale_init=1.5 * torch.ones(obs_dim)
        ).double()
    elif args.model == "lcmgp":
        num_gps = 9
        gp = LinearlyCoupledMaternGP(
            nu=1.5,
            obs_dim=obs_dim,
            num_gps=num_gps,
            length_scale_init=1.5 * torch.ones(num_gps),
        ).double()

    # set up optimizer
    adam = torch.optim.Adam(
        gp.parameters(),
        lr=args.init_learning_rate,
        betas=(args.beta1, 0.999),
        amsgrad=True,
    )
    # we decay the learning rate over the course of training
    gamma = (args.final_learning_rate / args.init_learning_rate) ** (
        1.0 / args.num_steps
    )
    scheduler = torch.optim.lr_scheduler.ExponentialLR(adam, gamma=gamma)

    report_frequency = 10

    # training loop
    for step in range(args.num_steps):
        loss = -gp.log_prob(data[0:T_train, :]).sum() / T_train
        loss.backward()
        adam.step()
        scheduler.step()

        if step % report_frequency == 0 or step == args.num_steps - 1:
            print("[step %03d]  loss: %.3f" % (step, loss.item()))

    # plot predictions for three output dimensions
    if args.plot:
        assert not args.test

        T_multistep = 49
        T_onestep = T_forecast - T_multistep

        # do rolling prediction
        print("doing one-step-ahead forecasting...")
        onestep_means, onestep_stds = np.zeros((T_onestep, obs_dim)), np.zeros(
            (T_onestep, obs_dim)
        )
        for t in range(T_onestep):
            # predict one step into the future, conditioning on all previous data.
            # note that each call to forecast() conditions on more data than the previous call
            dts = torch.tensor([1.0]).double()
            pred_dist = gp.forecast(data[0 : T_train + t, :], dts)
            onestep_means[t, :] = pred_dist.loc.data.numpy()
            if args.model == "imgp":
                onestep_stds[t, :] = pred_dist.scale.data.numpy()
            elif args.model == "lcmgp":
                onestep_stds[t, :] = pred_dist.covariance_matrix.diagonal(
                    dim1=-1, dim2=-2
                ).data.numpy()

        # do (non-rolling) multi-step forecasting
        print("doing multi-step forecasting...")
        dts = (1 + torch.arange(T_multistep)).double()
        pred_dist = gp.forecast(data[0 : T_train + T_onestep, :], dts)
        multistep_means = pred_dist.loc.data.numpy()
        if args.model == "imgp":
            multistep_stds = pred_dist.scale.data.numpy()
        elif args.model == "lcmgp":
            multistep_stds = pred_dist.covariance_matrix.diagonal(
                dim1=-1, dim2=-2
            ).data.numpy()

        import matplotlib

        matplotlib.use("Agg")  # noqa: E402
        import matplotlib.pyplot as plt

        f, axes = plt.subplots(3, 1, figsize=(12, 8), sharex=True)
        T = data.size(0)
        to_seconds = 117.0 / T

        for k, ax in enumerate(axes):
            which = [0, 4, 10][k]

            # plot raw data
            ax.plot(
                to_seconds * np.arange(T),
                data[:, which],
                "ko",
                markersize=2,
                label="Data",
            )

            # plot mean predictions for one-step-ahead forecasts
            ax.plot(
                to_seconds * (T_train + np.arange(T_onestep)),
                onestep_means[:, which],
                ls="solid",
                color="b",
                label="One-step",
            )
            # plot 90% confidence intervals for one-step-ahead forecasts
            ax.fill_between(
                to_seconds * (T_train + np.arange(T_onestep)),
                onestep_means[:, which] - 1.645 * onestep_stds[:, which],
                onestep_means[:, which] + 1.645 * onestep_stds[:, which],
                color="b",
                alpha=0.20,
            )

            # plot mean predictions for multi-step-ahead forecasts
            ax.plot(
                to_seconds * (T_train + T_onestep + np.arange(T_multistep)),
                multistep_means[:, which],
                ls="solid",
                color="r",
                label="Multi-step",
            )
            # plot 90% confidence intervals for multi-step-ahead forecasts
            ax.fill_between(
                to_seconds * (T_train + T_onestep + np.arange(T_multistep)),
                multistep_means[:, which] - 1.645 * multistep_stds[:, which],
                multistep_means[:, which] + 1.645 * multistep_stds[:, which],
                color="r",
                alpha=0.20,
            )

            ax.set_ylabel("$y_{%d}$" % (which + 1), fontsize=20)
            ax.tick_params(axis="both", which="major", labelsize=14)
            if k == 1:
                ax.legend(loc="upper left", fontsize=16)

        plt.tight_layout(pad=0.7)
        plt.savefig("eeg.{}.pdf".format(args.model))
