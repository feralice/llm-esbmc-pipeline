def dfxp2srt(dfxp_data):
    _x = functools.partial(xpath_with_ns, ns_map={
        'ttml': 'http://www.w3.org/ns/ttml',
        'ttaf1': 'http://www.w3.org/2006/10/ttaf1',
    })

    def parse_node(node):
        str_or_empty = functools.partial(str_or_none, default='')

        out = str_or_empty(node.text)

        for child in node:
            if child.tag in (_x('ttml:br'), _x('ttaf1:br'), 'br'):
                out += '\n' + str_or_empty(child.tail)
            elif child.tag in (_x('ttml:span'), _x('ttaf1:span'), 'span'):
                out += str_or_empty(parse_node(child))
            else:
                out += str_or_empty(xml.etree.ElementTree.tostring(child))

        return out

    dfxp = compat_etree_fromstring(dfxp_data.encode('utf-8'))
    out = []
    paras = dfxp.findall(_x('.//ttml:p')) or dfxp.findall(_x('.//ttaf1:p')) or dfxp.findall('.//p')

    if not paras:
        raise ValueError('Invalid dfxp/TTML subtitle')

    for para, index in zip(paras, itertools.count(1)):
        begin_time = parse_dfxp_time_expr(para.attrib['begin'])
        end_time = parse_dfxp_time_expr(para.attrib.get('end'))
        if not end_time:
            end_time = begin_time + parse_dfxp_time_expr(para.attrib['dur'])
        out.append('%d\n%s --> %s\n%s\n\n' % (
            index,
            srt_subtitles_timecode(begin_time),
            srt_subtitles_timecode(end_time),
            parse_node(para)))

    return ''.join(out)
