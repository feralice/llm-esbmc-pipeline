def find_hook(hook_name, hooks_dir='hooks'):
    if not os.path.isdir(hooks_dir):
        logger.debug('No hooks/dir in template_dir')
        return None

    for hook_file in os.listdir(hooks_dir):
        if valid_hook(hook_file, hook_name):
            return os.path.abspath(os.path.join(hooks_dir, hook_file))

    return None


def run_hook(hook_name, project_dir, context):
    script = find_hook(hook_name)
    if script is None:
        logger.debug('No %s hook found', hook_name)
        return
    logger.debug('Running hook %s', hook_name)
    run_script_with_context(script, project_dir, context)
