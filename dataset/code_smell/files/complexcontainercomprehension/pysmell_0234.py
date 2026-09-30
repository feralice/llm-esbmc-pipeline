# smell: ComplexContainerComprehension
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/django/db/models/expressions.py#L141-L146
# smelly line(s) in the original file: 143
# smelly line(s) in this file: 10
# ids: pysmell_0234
# note: Python 2 era source, kept as found
def _parse_expressions(self, *expressions):
    return [
        arg if hasattr(arg, 'resolve_expression') else (
            F(arg) if isinstance(arg, six.string_types) else Value(arg)
        ) for arg in expressions
    ]
