# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/django/db/migrations/operations/models.py#L414-L415
# smelly line(s) in the original file: 414
# smelly line(s) in this file: 8
# ids: pysmell_1964
# note: Python 2 era source, kept as found
def database_backwards(self, app_label, schema_editor, from_state, to_state):
    return self.database_forwards(app_label, schema_editor, from_state, to_state)
