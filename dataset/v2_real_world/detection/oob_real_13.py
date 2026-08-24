def tokenize(string, keep_zwj: bool) -> Iterator[Token]:
    """
    Finds unicode emoji in a string. Yields all normal characters as a named
    tuple :class:`Token` ``(char, char)`` and all emoji as :class:`Token` ``(chars, EmojiMatch)``.

    :param string: String contains unicode characters. MUST BE UNICODE.
    :param keep_zwj: Should ZWJ-characters (``\\u200D``) that join non-RGI emoji be
        skipped or should be yielded as normal characters
    :return: An iterable of tuples :class:`Token` ``(char, char)`` or :class:`Token` ``(chars, EmojiMatch)``
    """

    tree = get_search_tree()
    EMOJI_DATA = unicode_codes.EMOJI_DATA
    # result: [ Token(oldsubstring0, EmojiMatch), Token(char1, char1), ... ]
    result = []
    i = 0
    length = len(string)
    ignore = []  # index of chars in string that are skipped, i.e. the ZWJ-char in non-RGI-ZWJ-sequences
    while i < length:
        consumed = False
        char = string[i]
        if i in ignore:
            i += 1
            if char == _ZWJ and keep_zwj:
                result.append(Token(char, char))
            continue

        elif char in tree:
            j = i + 1
            sub_tree = tree[char]
            while j < length and string[j] in sub_tree:
                if j in ignore:
                    break
                sub_tree = sub_tree[string[j]]
                j += 1
            if 'data' in sub_tree:
                emj_data = sub_tree['data']
                code_points = string[i:j]

                # We cannot yield the result here, we need to defer
                # the call until we are sure that the emoji is finished
                # i.e. we're not inside an ongoing ZWJ-sequence
                match_obj = EmojiMatch(code_points, i, j, emj_data)

                i = j - 1
                consumed = True
                result.append(Token(code_points, match_obj))

        elif char == _ZWJ and result[-1].chars in EMOJI_DATA and string[i - 1] in tree:
            # the current char is ZWJ and the last match was an emoji
            ignore.append(i)
            if EMOJI_DATA[result[-1].chars]["status"] == unicode_codes.STATUS["component"]:
                # last match was a component, it could be ZWJ+EMOJI+COMPONENT
                # or ZWJ+COMPONENT
                i = i - sum(len(t.chars) for t in result[-2:])
                if string[i] == _ZWJ:
                    # It's ZWJ+COMPONENT, move one back
                    i += 1
                    del result[-1]
                else:
                    # It's ZWJ+EMOJI+COMPONENT, move two back
                    del result[-2:]
            else:
                # last match result[-1] was a normal emoji, move cursor
                # before the emoji
                i = i - len(result[-1].chars)
                del result[-1]
            continue

        elif result:
            yield from result
            result = []

        if not consumed and char != '\uFE0E' and char != '\uFE0F':
            result.append(Token(char, char))
        i += 1

    yield from result
