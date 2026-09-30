# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/ansible/ansible/blob/v1.9.2-0.1.rc1/v2/ansible/plugins/strategies/__init__.py#L86-L87
# smelly line(s) in the original file: 87
# smelly line(s) in this file: 9
# ids: pysmell_0034
# note: Python 2 era source, kept as found
def get_hosts_remaining(self, play):
    return [host for host in self._inventory.get_hosts(play.hosts) if host.name not in self._tqm._failed_hosts and host.get_name() not in self._tqm._unreachable_hosts]
