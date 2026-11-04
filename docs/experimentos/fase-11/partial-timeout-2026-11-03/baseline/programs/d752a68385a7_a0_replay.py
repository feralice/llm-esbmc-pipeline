











def replace_argument(a0=None, a1=None, a2=None) -> str:
    _stub_value: str = nondet_str()
    return _stub_value


class _Obj_command:
    def __init__(self) -> None:
        _field_script_parts: list[str] = nondet_list(3, elem_type=nondet_str())
        self.script_parts: list[str] = _field_script_parts
        _field_stderr: str = nondet_str()
        self.stderr: str = _field_stderr




def get_new_command(command: _Obj_command):
    # If --set-upstream or -u are passed, remove it and its argument. This is
    # because the remaining arguments are concatenated onto the command suggested
    # by git, which includes --set-upstream and its argument
    upstream_option_index = -1
    try:
        upstream_option_index = command.script_parts.index('--set-upstream')
    except ValueError:
        pass
    try:
        upstream_option_index = command.script_parts.index('-u')
    except ValueError:
        pass
    if upstream_option_index is not -1:
        command.script_parts.pop(upstream_option_index)
        command.script_parts.pop(upstream_option_index)

    push_upstream = command.stderr.split('\n')[-3].strip().partition('git ')[2]
    return replace_argument(" ".join(command.script_parts), 'push', push_upstream)


def _esbmc_main() -> None:
    command: _Obj_command = _Obj_command()
    get_new_command(command)


_esbmc_main()
