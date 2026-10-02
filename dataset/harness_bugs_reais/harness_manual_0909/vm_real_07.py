def pick_validation_enqueuer(uses_train_generator: bool) -> None:
    # Real code (keras/engine/training_generator.py:fit_generator, BugsInPy
    # keras bug #13): inside the branch that sets up the VALIDATION data
    # enqueuer, `val_enqueuer_gen = iter_sequence_infinite(generator)` reuses
    # the TRAINING generator variable instead of `val_data`, so validation
    # silently iterates over training data.
    assert not uses_train_generator


def main() -> None:
    uses_train_generator: bool = nondet_bool()
    pick_validation_enqueuer(uses_train_generator)


main()
