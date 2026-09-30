# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/django/contrib/admin/checks.py#L305-L320
# smelly line(s) in the original file: 305
# smelly line(s) in this file: 8
# ids: pysmell_1933
# note: Python 2 era source, kept as found
def _check_radio_fields_value(self, cls, model, val, label):
    """ Check type of a value of `radio_fields` dictionary. """

    from django.contrib.admin.options import HORIZONTAL, VERTICAL

    if val not in (HORIZONTAL, VERTICAL):
        return [
            checks.Error(
                "The value of '%s' must be either admin.HORIZONTAL or admin.VERTICAL." % label,
                hint=None,
                obj=cls,
                id='admin.E024',
            )
        ]
    else:
        return []
