def hooks_run_buggy(num_matching_hooks: int) -> int:
    # Real code (cookiecutter/hooks.py:find_hook, BugsInPy cookiecutter bug
    # #2): the buggy version returns on the FIRST matching hook file found
    # inside the os.listdir loop, so run_hook only ever executes one script
    # even when multiple hook files match the same hook name (e.g. both
    # pre_gen_project.py and pre_gen_project.sh present).
    if num_matching_hooks <= 0:
        return 0
    return 1


def hooks_run_correct(num_matching_hooks: int) -> int:
    return num_matching_hooks


def main() -> None:
    num_matching_hooks: int = nondet_int()
    __ESBMC_assume(num_matching_hooks >= 0 and num_matching_hooks <= 5)
    buggy: int = hooks_run_buggy(num_matching_hooks)
    correct: int = hooks_run_correct(num_matching_hooks)
    assert buggy == correct


main()
