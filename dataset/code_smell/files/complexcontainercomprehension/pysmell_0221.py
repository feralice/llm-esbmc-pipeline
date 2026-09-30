# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/django/db/backends/postgresql_psycopg2/introspection.py#L43-L56
# smelly line(s) in the original file: 54
# smelly line(s) in this file: 19
# ids: pysmell_0221
# note: Python 2 era source, kept as found
def get_table_list(self, cursor):
    """
    Returns a list of table and view names in the current database.
    """
    cursor.execute("""
        SELECT c.relname, c.relkind
        FROM pg_catalog.pg_class c
        LEFT JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE c.relkind IN ('r', 'v')
            AND n.nspname NOT IN ('pg_catalog', 'pg_toast')
            AND pg_catalog.pg_table_is_visible(c.oid)""")
    return [TableInfo(row[0], {'r': 't', 'v': 'v'}.get(row[1]))
            for row in cursor.fetchall()
            if row[0] not in self.ignored_tables]
