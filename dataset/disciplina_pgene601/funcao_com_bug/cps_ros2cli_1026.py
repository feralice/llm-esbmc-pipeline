class InterfaceFlags:
    def __str__(self):
        if not self.flags:
            return

        return self.flags.upper()


class NetworkReport:
    def report(self):
        """Print system and ROS network information."""
        if_stats = psutil.net_if_stats()

        network_report = Report('NETWORK CONFIGURATION')

        for interface, addrs in psutil.net_if_addrs().items():
            if_info = {
                'inet': None,
                'inet4': [],
                'ether': None,
                'inet6': [],
                'netmask': None,
                'device': interface,
                'flags': None,
                'mtu': None,
                'broadcast': None,
            }
            for addr in addrs:
                if addr.family == socket.AddressFamily.AF_INET:
                    if_info['inet'] = addr.address
                    if_info['inet4'].append(addr.address)
                    if_info['netmask'] = addr.netmask
                    if_info['broadcast'] = addr.broadcast
                elif addr.family == socket.AddressFamily.AF_INET6:
                    if_info['inet6'].append(addr.address)
                elif 'AF_PACKET' in socket.AddressFamily.__members__:
                    if addr.family == socket.AddressFamily.AF_PACKET:
                        # Loopback reports an all-zero MAC address, which is
                        # bogus and should not be reported
                        if addr.address != '00:00:00:00:00:00':
                            if_info['ether'] = addr.address

            if interface in if_stats:
                if_info['mtu'] = if_stats[interface].mtu

            flags = InterfaceFlags(interface)
            if_info['flags'] = str(flags)

            for k, v in if_info.items():
                if v:
                    network_report.add_to_report(k, v)
        return network_report
