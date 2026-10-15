def find_available_interfaces() -> List[str]:
    """Returns the names of all open can/vcan interfaces

    The function calls the ``ip link list`` command. If the lookup fails, an error
    is logged to the console and an empty list is returned.

    :return: The list of available and active CAN interfaces or an empty list of the command failed
    """

    try:
        command = ["ip", "-json", "link", "list", "up"]
        output_str = subprocess.check_output(command, text=True)
    except Exception:  # pylint: disable=broad-except
        # subprocess.CalledProcessError is too specific
        log.exception("failed to fetch opened can devices from ip link")
        return []

    try:
        output_json = json.loads(output_str)
    except json.JSONDecodeError:
        log.exception("Failed to parse ip link JSON output: %s", output_str)
        return []

    log.debug(
        "find_available_interfaces(): detected these interfaces (before filtering): %s",
        output_json,
    )

    interfaces = [i["ifname"] for i in output_json if i["link_type"] == "can"]
    return interfaces
