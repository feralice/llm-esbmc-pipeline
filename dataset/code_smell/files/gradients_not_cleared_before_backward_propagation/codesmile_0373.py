# smell: Gradients Not Cleared Before Backward Propagation (R9)
# validated by: SpecDetect4AI re-annotation of CodeSmile, adjudicated
# origin: https://github.com/KamruzzamanAsif/SpecDetect4AI-B903/blob/7576762f92b4205c9a995082edb215474b4e40d0/Evaluation/Ground_Truth_Construction_Process/Ground_Truth_CodeSmile/CodeSmile-Validation/experimental_kits/2/files/EvalID_30/train.py#L89-L203
# smelly line(s) in the original file: 160
# smelly line(s) in this file: 78
# ids: codesmile_0373
def training_function(args):
  # smddp example specifically tailored for p4d(e) instance types.
  local_rank = dist.get_rank() % 8
  seed = args.seed
  set_seed(seed)
  torch.cuda.set_device(local_rank)

  dataset = {
    'train': StubDataset(),
    'validation': StubDataset()
  }

  dtype = torch.bfloat16

  from transformers import LlamaConfig
  configuration = LlamaConfig(use_cache=False)
  from transformers.models.llama import LlamaForCausalLM
  with deepspeed.zero.Init(dtype=dtype, enabled=True):
    model = AutoModelForCausalLM.from_config(configuration)
  model.gradient_checkpointing_enable()

  train_dataset = dataset["train"]
  eval_dataset = dataset["validation"]
  train_dataloader, eval_dataloader = create_dataloaders(
    train_dataset, eval_dataset, dist.get_rank(), dist.get_world_size(), 
    seed, args.batch_size, args.batch_size)

  no_decay = ["bias", "LayerNorm.weight", "layer_norm.weight"]
  optimizer_grouped_parameters = [{
      "params": [p for n, p in model.named_parameters() if not any(nd in n for nd in no_decay)],
      "weight_decay": args.weight_decay,
    },{
      "params": [p for n, p in model.named_parameters() if any(nd in n for nd in no_decay)],
      "weight_decay": 0.0,
    }] 

  optimizer = torch.optim.AdamW(optimizer_grouped_parameters, lr=args.learning_rate)

   # Scheduler and math around the number of training steps.
  overrode_max_train_steps = False
  num_update_steps_per_epoch = math.ceil(len(train_dataloader) / args.gradient_accumulation_steps)
  if dist.get_rank()==0:
    print(f"Number of update steps per epoch {num_update_steps_per_epoch}")
  if args.max_train_steps is None:
    args.max_train_steps = args.num_train_epochs * num_update_steps_per_epoch
    overrode_max_train_steps = True

  lr_scheduler = get_scheduler(
    name=args.lr_scheduler_type,
    optimizer=optimizer,
    num_warmup_steps=args.num_warmup_steps * args.gradient_accumulation_steps,
    num_training_steps=args.max_train_steps * args.gradient_accumulation_steps,
  )

  model, optimizer, _, _ = deepspeed.initialize(
    model=model,
    optimizer=optimizer,
    model_parameters=model.parameters(),
    config=args.deepspeed_config
  )
  device = torch.device(f"cuda:{local_rank}")
  for epoch in range(args.num_train_epochs):
    model.train()
    total_steps=0
    ds_loss = torch.zeros(2).to(local_rank)

    for batch_idx, batch in enumerate(train_dataloader):
      batch = {k: v.to(device) for k, v in batch.items()}  
      output = model(**batch)
      if dist.get_rank() == 0: print(f"Processing training batch {batch_idx}")
      loss = output["loss"]
      loss.backward()
      ds_loss[0] += loss.item()
      ds_loss[1] += len(batch["input_ids"])
      optimizer.zero_grad()
      lr_scheduler.step()
      total_steps += 1
      if args.max_steps is not None and total_steps > args.max_steps:
        break

    torch.distributed.all_reduce(ds_loss, op=torch.distributed.ReduceOp.SUM)
    train_loss = ds_loss[0] / ds_loss[1]
    train_ppl = torch.exp(train_loss)

    if dist.get_rank()==0:
      print(f"******{epoch=}: {train_ppl=} {train_loss=}******")

    model.eval()
    eval_loss = 0
    ds_eval_loss = torch.zeros(2).to(local_rank)
    for steps, batch in enumerate(eval_dataloader):
      batch = {k: v.to(device) for k, v in batch.items()}

      if dist.get_rank() == 0: print(f"Performing validation on training batch {batch_idx}")
      with torch.no_grad():
        outputs = model(**batch)
      loss = outputs["loss"]
      ds_eval_loss[0] += loss.item()
      ds_eval_loss[1] += len(batch["input_ids"])
      if args.max_steps is not None and steps > args.max_steps:
        break

    torch.distributed.all_reduce(ds_eval_loss, op=torch.distributed.ReduceOp.SUM)
    eval_loss = ds_eval_loss[0] / ds_eval_loss[1]
    eval_ppl = torch.exp(eval_loss)

    if dist.get_rank()==0:
      print(f"*******{epoch=}: {eval_ppl=} {eval_loss=}*******")

    if args.max_steps is not None and total_steps > args.max_steps:
        break

  if dist.get_rank() == 0:
    print("Training done!")
  dist.barrier()
