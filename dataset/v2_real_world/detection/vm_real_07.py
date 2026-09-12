def fit_generator(model, generator, steps_per_epoch=None, epochs=1,
                   validation_data=None, validation_steps=None, val_gen=False):
    if do_validation:
        if val_gen and not isinstance(validation_data, Sequence):
            val_data = validation_data
            val_enqueuer = OrderedEnqueuer(val_data,
                                            use_multiprocessing=use_multiprocessing)
            val_enqueuer.start(workers=workers,
                                max_queue_size=max_queue_size)
            val_enqueuer_gen = val_enqueuer.get()
        elif val_gen:
            val_data = validation_data
            if isinstance(val_data, Sequence):
                val_enqueuer_gen = iter_sequence_infinite(generator)
            else:
                val_enqueuer_gen = val_data
