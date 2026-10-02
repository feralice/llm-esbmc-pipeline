def in_workers_buggy(assistant: bool, task_workers_nonempty: bool, worker_in_workers: bool) -> bool:
    return assistant or worker_in_workers


def in_workers_fixed(assistant: bool, task_workers_nonempty: bool, worker_in_workers: bool) -> bool:
    return (assistant and task_workers_nonempty) or worker_in_workers


def main() -> None:
    assistant: bool = True
    task_workers_nonempty: bool = False
    worker_in_workers: bool = False
    buggy: bool = in_workers_buggy(assistant, task_workers_nonempty, worker_in_workers)
    correct: bool = in_workers_fixed(assistant, task_workers_nonempty, worker_in_workers)
    assert buggy == correct


main()
