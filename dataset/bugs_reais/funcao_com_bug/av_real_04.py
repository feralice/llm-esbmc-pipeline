def _partition_tasks(worker):
    """
    Takes a worker and sorts out tasks based on their status.
    Still_pending_not_ext is only used to get upstream_failure, upstream_missing_dependency and run_by_other_worker
    """
    task_history = worker._add_task_history
    pending_tasks = {task for(task, status, ext) in task_history if status == 'PENDING'}
    set_tasks = {}
    set_tasks["completed"] = {task for (task, status, ext) in task_history if status == 'DONE' and task in pending_tasks}
    set_tasks["already_done"] = {task for (task, status, ext) in task_history
                                 if status == 'DONE' and task not in pending_tasks and task not in set_tasks["completed"]}
    set_tasks["failed"] = {task for (task, status, ext) in task_history if status == 'FAILED'}
    set_tasks["scheduling_error"] = {task for(task, status, ext) in task_history if status == 'UNKNOWN'}
    set_tasks["still_pending_ext"] = {task for (task, status, ext) in task_history
                                      if status == 'PENDING' and task not in set_tasks["failed"] and task not in set_tasks["completed"] and not ext}
    set_tasks["still_pending_not_ext"] = {task for (task, status, ext) in task_history
                                          if status == 'PENDING' and task not in set_tasks["failed"] and task not in set_tasks["completed"] and ext}
    set_tasks["run_by_other_worker"] = set()
    set_tasks["upstream_failure"] = set()
    set_tasks["upstream_missing_dependency"] = set()
    set_tasks["upstream_run_by_other_worker"] = set()
    set_tasks["upstream_scheduling_error"] = set()
    set_tasks["not_run"] = set()
    return set_tasks


def _summary_format(set_tasks, worker):
    group_tasks = {}
    for status, task_dict in set_tasks.items():
        group_tasks[status] = _group_tasks_by_name_and_status(task_dict)
    comments = _get_comments(group_tasks)
    num_all_tasks = sum([len(set_tasks["already_done"]),
                         len(set_tasks["completed"]), len(set_tasks["failed"]),
                         len(set_tasks["scheduling_error"]),
                         len(set_tasks["still_pending_ext"]),
                         len(set_tasks["still_pending_not_ext"])])
    str_output = ''
    str_output += 'Scheduled {0} tasks of which:\n'.format(num_all_tasks)
    for status in _ORDERED_STATUSES:
        if status not in comments:
            continue
        str_output += '{0}'.format(comments[status])
        if status != 'still_pending':
            str_output += '{0}\n'.format(_get_str(group_tasks[status], status in _PENDING_SUB_STATUSES))
    ext_workers = _get_external_workers(worker)
    group_tasks_ext_workers = {}
    for ext_worker, task_dict in ext_workers.items():
        group_tasks_ext_workers[ext_worker] = _group_tasks_by_name_and_status(task_dict)
    if len(ext_workers) > 0:
        str_output += "\nThe other workers were:\n"
        count = 0
        for ext_worker, task_dict in ext_workers.items():
            if count > 3 and count < len(ext_workers) - 1:
                str_output += "    and {0} other workers".format(len(ext_workers) - count)
                break
            str_output += "    - {0} ran {1} tasks\n".format(ext_worker, len(task_dict))
            count += 1
        str_output += '\n'
    if num_all_tasks == sum([len(set_tasks["already_done"]),
                             len(set_tasks["scheduling_error"]),
                             len(set_tasks["still_pending_ext"]),
                             len(set_tasks["still_pending_not_ext"])]):
        if len(ext_workers) == 0:
            str_output += '\n'
        str_output += 'Did not run any tasks'
    smiley = ""
    reason = ""
    if set_tasks["failed"]:
        smiley = ":("
        reason = "there were failed tasks"
        if set_tasks["scheduling_error"]:
            reason += " and tasks whose scheduling failed"
    elif set_tasks["scheduling_error"]:
        smiley = ":("
        reason = "there were tasks whose scheduling failed"
    elif set_tasks["not_run"]:
        smiley = ":|"
        reason = "there were tasks that were not granted run permission by the scheduler"
    elif set_tasks["still_pending_ext"]:
        smiley = ":|"
        reason = "there were missing external dependencies"
    else:
        smiley = ":)"
        reason = "there were no failed tasks or missing external dependencies"
    str_output += "\nThis progress looks {0} because {1}".format(smiley, reason)
    if num_all_tasks == 0:
        str_output = 'Did not schedule any tasks'
    return str_output
