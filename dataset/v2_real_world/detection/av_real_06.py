@utils.git_support
def get_new_command(command, settings):
    return '{} --staged'.format(command.script)
