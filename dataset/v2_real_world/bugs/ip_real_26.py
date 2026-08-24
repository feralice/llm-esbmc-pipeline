def allow_reschedule_buggy(task_running_or_batch: bool, status_is_pending: bool, new_deps: bool) -> bool:
    return (not (task_running_or_batch and status_is_pending)) or new_deps


def allow_reschedule_fixed(task_running_or_batch: bool, status_not_done_failed_running: bool, worker_mismatch: bool, new_deps: bool) -> bool:
    return (not (task_running_or_batch and (status_not_done_failed_running or worker_mismatch))) or new_deps


def main() -> None:
    task_running_or_batch: bool = True
    status_is_pending: bool = False
    status_not_done_failed_running: bool = False
    worker_mismatch: bool = True
    new_deps: bool = False
    buggy: bool = allow_reschedule_buggy(task_running_or_batch, status_is_pending, new_deps)
    correct: bool = allow_reschedule_fixed(task_running_or_batch, status_not_done_failed_running, worker_mismatch, new_deps)
    assert buggy == correct


main()
