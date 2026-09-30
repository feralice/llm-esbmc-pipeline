# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/django/db/migrations/operations/fields.py#L252-L266
# smelly line(s) in the original file: 255
# smelly line(s) in this file: 11
# ids: pysmell_0229
# note: Python 2 era source, kept as found
def state_forwards(self, app_label, state):
    # Rename the field
    state.models[app_label, self.model_name_lower].fields = [
        (self.new_name if n == self.old_name else n, f)
        for n, f in state.models[app_label, self.model_name_lower].fields
    ]
    # Fix index/unique_together to refer to the new field
    options = state.models[app_label, self.model_name_lower].options
    for option in ('index_together', 'unique_together'):
        if option in options:
            options[option] = [
                [self.new_name if n == self.old_name else n for n in together]
                for together in options[option]
            ]
    state.reload_model(app_label, self.model_name_lower)
