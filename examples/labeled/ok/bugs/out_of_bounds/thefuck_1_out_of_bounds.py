# Extracted from thefuck/rules/pip_unknown_command.py — The Fuck project
# Source: BugsInPy thefuck #1
# Bug: re.findall(...)[0] raises IndexError when the pattern has no match in output
# Real fix: regex pattern broadened to match more command name formats
import re

def get_new_command(output: str, script: str) -> str:
    broken_cmd = re.findall(r'ERROR: unknown command "([a-z]+)"', output)[0]
    new_cmd = re.findall(r'maybe you meant "([a-z]+)"', output)[0]
    return script.replace(broken_cmd, new_cmd)
