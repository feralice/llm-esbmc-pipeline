# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/tests/auth_tests/models/with_foreign_key.py#L13-L17
# smelly line(s) in the original file: 13
# smelly line(s) in this file: 8
# ids: pysmell_1988
# note: Python 2 era source, kept as found
def create_superuser(self, username, email, group, password):
    user = self.model(username_id=username, email_id=email, group_id=group)
    user.set_password(password)
    user.save(using=self._db)
    return user
