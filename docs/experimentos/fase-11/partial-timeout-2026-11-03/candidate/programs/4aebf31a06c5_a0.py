def _esbmc_none_attribute(value_is_none: bool) -> bool:
    if value_is_none:
        raise AttributeError("'NoneType' object has no attribute")
    return True


def _esbmc_none_type(value_is_none: bool) -> bool:
    if value_is_none:
        raise TypeError("'NoneType' object does not support this operation")
    return True







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
        _esbmc_none_attribute(command.script_parts is None); command.script_parts.pop(upstream_option_index)
        command.script_parts.pop(upstream_option_index)

    pass



def _esbmc_main() -> None:
    command: _Obj_command = _Obj_command()
    get_new_command(command)


_esbmc_main()
