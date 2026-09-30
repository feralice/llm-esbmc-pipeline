# smell: LongMessageChain
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/tests/unit/ec2/test_volume.py#L191-L200
# smelly line(s) in the original file: 198
# smelly line(s) in this file: 15
# ids: pysmell_1167
# note: Python 2 era source, kept as found
def test_snapshots_returns_snapshots(self):
    snapshot_one = Snapshot()
    snapshot_one.volume_id = 1
    snapshot_two = Snapshot()
    snapshot_two.volume_id = 2

    self.volume_one.connection = mock.Mock()
    self.volume_one.connection.get_all_snapshots.return_value = [snapshot_one, snapshot_two]
    retval = self.volume_one.snapshots()
    self.assertEqual(retval, [snapshot_one])
