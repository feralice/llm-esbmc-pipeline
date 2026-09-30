# smell: LongTernaryConditionalExpression
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/tornadoweb/tornado/blob/v4.2.0/tornado/test/escape_test.py#L126-L126
# smelly line(s) in the original file: 126
# smelly line(s) in this file: 8
# ids: pysmell_2080
# note: Python 2 era source, kept as found
{"extra_params": lambda href: 'class="internal"' if href.startswith("http://www.internal-link.com") else 'rel="nofollow" class="external"'},
