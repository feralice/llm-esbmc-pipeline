class YoutubeDL:
    def _build_format_filter(self, filter_spec):
        STR_OPERATORS = {
            '=': operator.eq,
            '^=': lambda attr, value: attr.startswith(value),
            '$=': lambda attr, value: attr.endswith(value),
            '*=': lambda attr, value: value in attr,
        }
        str_operator_rex = re.compile(r'''(?x)
            \s*(?P<key>ext|acodec|vcodec|container|protocol|format_id)
            \s*(?P<negation>!\s*)?(?P<op>%s)(?P<none_inclusive>\s*\?)?
            \s*(?P<value>[a-zA-Z0-9._-]+)
            \s*$
            ''' % '|'.join(map(re.escape, STR_OPERATORS.keys())))
        m = str_operator_rex.search(filter_spec)
        if m:
            comparison_value = m.group('value')
            str_op = STR_OPERATORS[m.group('op')]
            if m.group('negation'):
                op = lambda attr, value: not str_op
            else:
                op = str_op
