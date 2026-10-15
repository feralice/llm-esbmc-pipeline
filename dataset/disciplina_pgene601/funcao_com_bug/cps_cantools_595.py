class SystemLoader:
    def _load_comments(self, node):
        result = {}

        for l_2 in self._get_arxml_children(node, ['DESC', '*L-2']):
            lang = l_2.attrib.get('L', 'EN')

            # remove leading and trailing white space from each line
            # of multi-line comments
            tmp = [ x.strip() for x in l_2.text.split('\n') ]
            result[lang] = '\n'.join(tmp)

        if len(result) == 0:
            return None

        return result
