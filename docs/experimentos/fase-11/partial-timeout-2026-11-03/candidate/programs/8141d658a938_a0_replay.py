from typing import Optional












class _Obj_command:
    def __init__(self) -> None:
        _field_stderr: Optional[str] = None
        if nondet_bool():
            _field_stderr = nondet_str()
        self.stderr: Optional[str] = _field_stderr
        _field_stdout: Optional[str] = None
        if nondet_bool():
            _field_stdout = nondet_str()
        self.stdout: Optional[str] = _field_stdout

patterns = ['permission denied',
            'EACCES',
            'pkg: Insufficient privileges',
            'you cannot perform this operation unless you are root',
            'non-root users cannot',
            'Operation not permitted',
            'root privilege',
            'This command has to be run under the root user.',
            'This operation requires root.',
            'requested operation requires superuser privilege',
            'must be run as root',
            'must run as root',
            'must be superuser',
            'must be root',
            'need to be root',
            'need root',
            'only root can ',
            'You don\'t have access to the history DB.',
            'authentication is required',
            'eDSPermissionError']


def match(command: _Obj_command):
    for pattern in patterns:
        if pattern.lower() in command.stderr.lower()\
                or pattern.lower() in command.stdout.lower():
            return True
    return False


def _esbmc_main() -> None:
    command: _Obj_command = _Obj_command()
    match(command)


_esbmc_main()
