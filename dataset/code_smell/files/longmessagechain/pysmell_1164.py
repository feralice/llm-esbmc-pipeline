# smell: LongMessageChain
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/tests/unit/ec2/test_address.py#L32-L41
# smelly line(s) in the original file: 34
# smelly line(s) in this file: 10
# ids: pysmell_1164
# note: Python 2 era source, kept as found
def test_associate_calls_connection_associate_address_with_correct_args(self):
    self.address.associate(1)
    self.address.connection.associate_address.assert_called_with(
        instance_id=1,
        public_ip="192.168.1.1",
        allow_reassociation=False,
        network_interface_id=None,
        private_ip_address=None,
        dry_run=False
    )
