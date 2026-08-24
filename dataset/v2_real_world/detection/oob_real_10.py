def _wrap_text_to_colwidths(list_of_lists, colwidths, numparses=True):
    numparses = _expand_iterable(numparses, len(list_of_lists[0]), True)

    result = []

    for row in list_of_lists:
        new_row = []
        for cell, width, numparse in zip(row, colwidths, numparses):
            if _isnumber(cell) and numparse:
                new_row.append(cell)
                continue

            if width is not None:
                wrapper = _CustomTextWrap(width=width)
                # Cast based on our internal type handling
                # Any future custom formatting of types (such as datetimes)
                # may need to be more explicit than just `str` of the object
                casted_cell = (
                    str(cell) if _isnumber(cell) else _type(cell, numparse)(cell)
                )
                wrapped = [
                    "\n".join(wrapper.wrap(line))
                    for line in casted_cell.splitlines()
                    if line.strip() != ""
                ]
                new_row.append("\n".join(wrapped))
            else:
                new_row.append(cell)
        result.append(new_row)

    return result
