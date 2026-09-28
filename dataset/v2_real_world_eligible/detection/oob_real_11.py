def wcswidth(
    pwcs: str,
    n: Optional[int] = None,
    unicode_version: str = 'auto',
    ambiguous_width: int = 1,
) -> int:
    """
    Given a unicode string, return its printable length on a terminal.

    See :ref:`Specification` for details of cell measurement.

    This implementation differs from Markus Khun's original POSIX C implementation, in that this
    ``wcswidth()`` processes graphemes strings yielded by :func:`wcwidth.iter_graphemes` defined by
    `Unicode Standard Annex #29`_. POSIX wcswidth(3) is not grapheme-aware and does not measure many
    kinds of Emojis or complex scripts correctly.

    :param pwcs: Measure width of given unicode string.
    :param n: When ``n`` is None (default), return the length of the entire
        string, otherwise only the first ``n`` characters are measured.
    :param unicode_version: Ignored. Retained for backwards compatibility.

        .. deprecated:: 0.3.0
           Only the latest Unicode version is now shipped.

    :param ambiguous_width: Width to use for East Asian Ambiguous (A)
        characters. Default is ``1`` (narrow). Set to ``2`` for CJK contexts.
    :returns: The width, in cells, needed to display the first ``n`` characters
        of the unicode string ``pwcs``.  Returns ``-1`` for C0 and C1 control
        characters!

    .. _`Unicode Standard Annex #29`: https://www.unicode.org/reports/tr29/
    """
    # pylint: disable=unused-argument,too-many-locals,too-many-statements,redefined-variable-type
    # pylint: disable=too-complex,too-many-branches,duplicate-code,too-many-nested-blocks

    # Fast path: pure ASCII printable strings are always width == length
    if n is None and pwcs.isascii() and pwcs.isprintable():
        return len(pwcs)

    _wcwidth = wcwidth if ambiguous_width == 1 else lambda c: wcwidth(c, 'auto', ambiguous_width)

    end = len(pwcs) if n is None else n
    total_width = 0
    idx = 0

    last_measured_idx = -2  # -2 sentinel blocks VS16/VS15 (no base available)
    last_measured_ucs = -1
    last_measured_w = 0
    prev_was_virama = False
    cluster_width = 0
    vs16_nw_table = VS16_NARROW_TO_WIDE['9.0.0']
    vs15_wn_table = VS15_WIDE_TO_NARROW['9.0.0']
    _bisearch = bisearch

    while idx < end:
        char = pwcs[idx]
        ucs = ord(char)

        # 5. ZWJ (U+200D): consumed without contributing width.
        # Virama codepoints are treated as zero-width combining marks (Mn). When a
        # virama+consonant sequence forms a conjunct, its width is capped at 2 cells.

        # ZWJ (U+200D)
        if ucs == 0x200D:
            if prev_was_virama:
                idx += 1
            elif idx + 1 < end:
                last_measured_w = 0
                prev_was_virama = False
                idx += 2
            else:
                prev_was_virama = False
                idx += 1
            continue

        # 6. VS16 (U+FE0F): converts preceding narrow character to wide.
        if ucs == 0xFE0F and last_measured_idx >= 0:
            if _bisearch(last_measured_ucs, vs16_nw_table):
                cluster_width = 2
            last_measured_idx = -2
            idx += 1
            continue

        # VS15 (U+FE0E): text variation selector, requests narrow presentation.
        if ucs == 0xFE0E and last_measured_idx >= 0:
            if bisearch(last_measured_ucs, vs15_wn_table) and last_measured_w == 2:
                total_width -= 1
            idx += 1
            continue

        # 7. Regional Indicator & Fitzpatrick (both above BMP)
        if ucs > 0xFFFF:
            if ucs in _REGIONAL_INDICATOR_SET:
                ri_before = 0
                j = idx - 1
                while j >= 0 and ord(pwcs[j]) in _REGIONAL_INDICATOR_SET:
                    ri_before += 1
                    j -= 1
                if ri_before % 2 == 1:
                    last_measured_ucs = ucs
                    idx += 1
                    continue
            elif (_FITZPATRICK_RANGE[0] <= ucs <= _FITZPATRICK_RANGE[1]
                  and last_measured_ucs in _EMOJI_ZWJ_SET):
                idx += 1
                continue

        # 8. Normal character: measure with wcwidth
        w = _wcwidth(char)
        if w < 0:
            return -1
        if w > 0:
            if prev_was_virama:
                cluster_width = 2
            elif cluster_width:
                total_width += cluster_width
                cluster_width = w
            else:
                cluster_width = w

            last_measured_idx = idx
            last_measured_ucs = ucs
            last_measured_w = w
            prev_was_virama = False
        elif ucs in _ISC_VIRAMA_SET:
            prev_was_virama = True
        elif last_measured_idx >= 0 and _bisearch(ucs, _CATEGORY_MC_TABLE):
            cluster_width = 2
            last_measured_idx = -2
            prev_was_virama = False
        else:
            prev_was_virama = False
        idx += 1

    if cluster_width:
        total_width += cluster_width
    return total_width
