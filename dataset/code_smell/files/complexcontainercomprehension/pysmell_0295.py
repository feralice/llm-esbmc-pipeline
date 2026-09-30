# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/tests/schema/tests.py#L87-L103
# smelly line(s) in the original file: 90
# smelly line(s) in this file: 11
# ids: pysmell_0295
# note: Python 2 era source, kept as found
def column_classes(self, model):
    with connection.cursor() as cursor:
        columns = {
            d[0]: (connection.introspection.get_field_type(d[1], d), d)
            for d in connection.introspection.get_table_description(
                cursor,
                model._meta.db_table,
            )
        }
    # SQLite has a different format for field_type
    for name, (type, desc) in columns.items():
        if isinstance(type, tuple):
            columns[name] = (type[0], desc)
    # SQLite also doesn't error properly
    if not columns:
        raise DatabaseError("Table does not exist (empty pragma)")
    return columns
