def get_new_command_buggy(script: str) -> str:
    return 'open http://' + script[5:]


def get_new_command_fixed(script: str) -> str:
    return script.replace('open ', 'open http://')


def main() -> None:
    script: str = "open open google.com"
    buggy: str = get_new_command_buggy(script)
    correct: str = get_new_command_fixed(script)
    assert buggy == correct


main()
