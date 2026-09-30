# smell: Gradients Not Cleared Before Backward Propagation (R9)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_29/train.py#L45-L184
# smelly line(s) in the original file: 120, 123
# smelly line(s) in this file: 82, 85
# ids: codesmile_0366, codesmile_0367
def main(args):
    ### INIT DISTRIBUTED
    args.distributed_world_size = int(os.environ.get('WORLD_SIZE', 1))
    args.local_rank = int(os.environ.get('LOCAL_RANK', 0))
    if args.distributed_world_size > 1:
        dist.init_process_group(backend='nccl', init_method='env://')
        print_once(f'Distributed training with {args.distributed_world_size} GPUs')
        args.distributed_rank = dist.get_rank()
        torch.cuda.set_device(args.local_rank)
        torch.cuda.synchronize()

    # Enable CuDNN autotuner
    nproc_per_node = torch.cuda.device_count()
    if args.affinity != 'disabled':
        affinity = gpu_affinity.set_affinity(
                args.local_rank,
                nproc_per_node,
                args.affinity
            )
        print(f'{args.local_rank}: thread affinity: {affinity}')

    torch.backends.cudnn.benchmark = True

    if args.seed:
        np.random.seed(args.seed)
        torch.manual_seed(args.seed)
        torch.cuda.manual_seed(args.seed)

    setup_logger(args)

    config = CONFIGS[args.dataset]()
    if args.overwrite_config:
        config.__dict__.update(json.loads(args.overwrite_config))

    dllogger.log(step='HPARAMS', data={**vars(args), **vars(config)}, verbosity=1)

    train_loader, valid_loader, test_loader = load_dataset(args, config)

    model = TemporalFusionTransformer(config).cuda()
    if args.ema_decay:
        model_ema = ModelEma(model, decay=args.ema_decay)

    # Run dummy iteration to initialize lazy modules
    dummy_batch = next(iter(train_loader))
    dummy_batch = {key: tensor.cuda() if tensor.numel() else None for key, tensor in dummy_batch.items()}
    model(dummy_batch)

    criterion = QuantileLoss(config).cuda()
    optimizer = FusedAdam(model.parameters(), lr=args.lr)
    if args.distributed_world_size > 1:
        model = DDP(model, device_ids=[args.local_rank], output_device=args.local_rank, find_unused_parameters=True)


    print_once('Model params: {}'.format(sum(p.numel() for p in model.parameters())))
    global_step = 0
    perf_meter = PerformanceMeter(benchmark_mode=not args.disable_benchmark)
    if args.use_amp:
        scaler = amp.GradScaler(init_scale=32768.0)

    for epoch in range(args.epochs):
        start = time.time()
        dllogger.log(step=global_step, data={'epoch': epoch}, verbosity=1)

        model.train() 
        for local_step, batch in enumerate(train_loader):
            perf_meter.reset_current_lap()
            batch = {key: tensor.cuda() if tensor.numel() else None for key, tensor in batch.items()}
            with torch.jit.fuser("fuser2"), amp.autocast(enabled=args.use_amp):
                predictions = model(batch)
                targets = batch['target'][:,config.encoder_length:,:]
                p_losses = criterion(predictions, targets)
                loss = p_losses.sum()
            if global_step == 0 and args.ema_decay:
                model_ema(batch)
            if args.use_amp:
                scaler.scale(loss).backward()

            else:
                loss.backward()
            if not args.grad_accumulation or (global_step+1) % args.grad_accumulation == 0:
                if args.use_amp:
                    scaler.unscale_(optimizer)
                if args.clip_grad:
                    torch.nn.utils.clip_grad_norm_(model.parameters(), args.clip_grad)
                if args.use_amp:
                    scaler.step(optimizer)
                    scaler.update()
                else:
                    optimizer.step()
                optimizer.zero_grad()
                if args.ema_decay:
                    model_ema.update(model)

            if args.distributed_world_size > 1:
                dist.all_reduce(p_losses)
                p_losses /= args.distributed_world_size
                loss = p_losses.sum()

            torch.cuda.synchronize()
            ips = perf_meter.update(args.batch_size * args.distributed_world_size,
                    exclude_from_total=local_step in [0, 1, 2, len(train_loader)-1])

            log_dict = {'P10':p_losses[0].item(), 'P50':p_losses[1].item(), 'P90':p_losses[2].item(), 'loss': loss.item(), 'items/s':ips}
            dllogger.log(step=global_step, data=log_dict, verbosity=1)
            global_step += 1

        validate(args, config, model_ema if args.ema_decay else model, criterion, valid_loader, global_step)

        if validate.early_stop_c >= args.early_stopping:
            print_once('Early stopping')
            break

    ### TEST PHASE ###
    state_dict = torch.load(os.path.join(args.results, 'checkpoint.pt'), map_location='cpu')
    if isinstance(model, DDP):
        model.module.load_state_dict(state_dict['model'])
    else:
        model.load_state_dict(state_dict['model'])
    model.cuda().eval()

    tgt_scalers = pickle.load(open(os.path.join(args.data_path, 'tgt_scalers.bin'), 'rb'))
    cat_encodings = pickle.load(open(os.path.join(args.data_path,'cat_encodings.bin'), 'rb'))

    unscaled_predictions, unscaled_targets, _, _ = predict(args, config, model, test_loader, tgt_scalers, cat_encodings)

    unscaled_predictions = torch.from_numpy(unscaled_predictions).contiguous()
    unscaled_targets = torch.from_numpy(unscaled_targets).contiguous()

    losses = QuantileLoss(config)(unscaled_predictions, unscaled_targets)
    normalizer = unscaled_targets.abs().mean()
    quantiles = 2 * losses / normalizer

    if args.distributed_world_size > 1:
        quantiles = quantiles.cuda()
        dist.all_reduce(quantiles)
        quantiles /= args.distributed_world_size

    quantiles = {'test_p10': quantiles[0].item(), 'test_p50': quantiles[1].item(), 'test_p90': quantiles[2].item(), 'sum':sum(quantiles).item()}
    finish_log = {**quantiles, 'average_ips':perf_meter.avg, 'convergence_step':validate.conv_step}
    dllogger.log(step=(), data=finish_log, verbosity=1)
