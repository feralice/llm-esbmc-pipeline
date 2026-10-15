def _check_network_config_helper(ifcfg_ifaces: dict) -> Tuple[bool, bool, bool]:
    """Check if loopback and multicast IP addresses are found."""
    has_loopback, has_non_loopback, has_multicast = False, False, False
    for name, iface in ifcfg.interfaces().items():
        flags = iface.get('flags').lower()
        if 'loopback' in flags:
            has_loopback = True
        else:
            has_non_loopback = True
        if 'multicast' in flags:
            has_multicast = True
    return has_loopback, has_non_loopback, has_multicast
