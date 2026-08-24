def summary_smiley(ever_failed: bool, completed: bool) -> str:
    # Real code (luigi/execution_summary.py, _partition_tasks + _summary_format,
    # BugsInPy luigi bug #9): before the fix, set_tasks["failed"] held every
    # task that ever had a FAILED entry in its status history, even if a later
    # retry made it DONE. The fix renames that set to "ever_failed" and computes
    # the real "failed" set as ever_failed - completed, so a task that
    # eventually succeeds after a retry no longer counts as failed for the
    # run's pass/fail summary.
    failed: bool = ever_failed
    if failed:
        return ":("
    return ":)"


def main() -> None:
    ever_failed: bool = nondet_bool()
    completed: bool = nondet_bool()
    __ESBMC_assume(ever_failed and completed)
    smiley: str = summary_smiley(ever_failed, completed)
    assert smiley == ":)"


main()
