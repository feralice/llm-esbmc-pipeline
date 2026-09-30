# smell: LongMessageChain
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/tests/unit/ec2/test_volume.py#L102-L111
# smelly line(s) in the original file: 103
# smelly line(s) in this file: 9
# ids: pysmell_1166
# note: Python 2 era source, kept as found
def test_update_with_result_set_greater_than_0_updates_dict(self):
    self.volume_two.connection.get_all_volumes.return_value = [self.volume_one]
    self.volume_two.update()

    assert all([self.volume_two.create_time == 5,
                self.volume_two.status == "one_status",
                self.volume_two.size == "one_size",
                self.volume_two.snapshot_id == 1,
                self.volume_two.attach_data == self.attach_data,
                self.volume_two.zone == "one_zone"])
