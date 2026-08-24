class parser:
    def _parse(self, timestr, dayfirst=None, yearfirst=None, fuzzy=False,
               fuzzy_with_tokens=False):
        """
        Private method which performs the heavy lifting of parsing, called from
        ``parse()``, which passes on its ``kwargs`` to this function.

        :param timestr:
            The string to parse.

        :param dayfirst:
            Whether to interpret the first value in an ambiguous 3-integer date
            (e.g. 01/05/09) as the day (``True``) or month (``False``). If
            ``yearfirst`` is set to ``True``, this distinguishes between YDM
            and YMD. If set to ``None``, this value is retrieved from the
            current :class:`parserinfo` object (which itself defaults to
            ``False``).

        :param yearfirst:
            Whether to interpret the first value in an ambiguous 3-integer date
            (e.g. 01/05/09) as the year. If ``True``, the first number is taken
            to be the year, otherwise the last number is taken to be the year.
            If this is set to ``None``, the value is retrieved from the current
            :class:`parserinfo` object (which itself defaults to ``False``).

        :param fuzzy:
            Whether to allow fuzzy parsing, allowing for string like "Today is
            January 1, 2047 at 8:21:00AM".

        :param fuzzy_with_tokens:
            If ``True``, ``fuzzy`` is automatically set to True, and the parser
            will return a tuple where the first element is the parsed
            :class:`datetime.datetime` datetimestamp and the second element is
            a tuple containing the portions of the string which were ignored:

            .. doctest::

                >>> from dateutil.parser import parse
                >>> parse("Today is January 1, 2047 at 8:21:00AM", fuzzy_with_tokens=True)
                (datetime.datetime(2047, 1, 1, 8, 21), (u'Today is ', u' ', u'at '))

        """
        if fuzzy_with_tokens:
            fuzzy = True

        info = self.info

        if dayfirst is None:
            dayfirst = info.dayfirst

        if yearfirst is None:
            yearfirst = info.yearfirst

        res = self._result()
        l = _timelex.split(timestr)         # Splits the timestr into tokens
        tokens = l # alias that is easier to grep

        skipped_idxs = set()

        # year/month/day list
        ymd = _ymd(timestr)

        len_l = len(l)
        i = 0
        try:
            while i < len_l:

                # Check if it's a number
                try:
                    value_repr = l[i]
                    value = float(value_repr)
                except ValueError:
                    value = None

                if value is not None:
                    # Token is a number
                    len_li = len(l[i])

                    if (len(ymd) == 3 and len_li in (2, 4)
                        and res.hour is None and (i+1 >= len_l or (l[i+1] != ':' and
                                                  info.hms(l[i+1]) is None))):
                        # 19990101T23[59]
                        s = l[i]
                        res.hour = int(s[:2])

                        if len_li == 4:
                            res.minute = int(s[2:])
                        i += 1

                    elif len_li == 6 or (len_li > 6 and l[i].find('.') == 6):
                        # YYMMDD or HHMMSS[.ss]
                        s = l[i]

                        if not ymd and '.' not in l[i]:
                            #ymd.append(info.convertyear(int(s[:2])))

                            ymd.append(s[:2])
                            ymd.append(s[2:4])
                            ymd.append(s[4:])
                        else:
                            # 19990101T235959[.59]
                            res.hour = int(s[:2])
                            res.minute = int(s[2:4])
                            res.second, res.microsecond = _parsems(s[4:])
                        i += 1

                    elif len_li in (8, 12, 14):
                        # YYYYMMDD
                        s = l[i]
                        ymd.append(s[:4], 'Y')
                        ymd.append(s[4:6])
                        ymd.append(s[6:8])

                        if len_li > 8:
                            res.hour = int(s[8:10])
                            res.minute = int(s[10:12])

                            if len_li > 12:
                                res.second = int(s[12:])
                        i += 1

                    elif ((i+1 < len_l and info.hms(l[i+1]) is not None)
                        or (i+2 < len_l and l[i+1] == ' ' and info.hms(l[i+2]) is not None)
                            ):
                        # HH[ ]h or MM[ ]m or SS[.ss][ ]s
                        if l[i+1] == ' ':
                            i += 1

                        idx = info.hms(l[i+1])

                        while True:
                            if idx == 0:
                                res.hour = int(value)
                                if value % 1:
                                    res.minute = int(60*(value % 1))

                            elif idx == 1:
                                (res.minute, res.second) = _parse_min_sec(value)

                            elif idx == 2:
                                (res.second, res.microsecond) = _parsems(value_repr)


                            if i+2 >= len_l or idx == 2:
                                i += 1
                                break

                            # 12h00
                            try:
                                value_repr = l[i+2]
                                value = float(value_repr)
                            except ValueError:
                                i += 1
                                break
                            else:
                                idx += 1

                                if i+3 < len_l:
                                    newidx = info.hms(l[i+3])

                                    if newidx is not None:
                                        idx = newidx
                                i += 2

                        i += 1

                    elif (i+1 == len_l and l[i-1] == ' ' and info.hms(l[i-2]) is not None):
                        # X h MM or X m SS
                        idx = info.hms(l[i-2])

                        if idx == 0:               # h
                            (res.minute, res.second) = _parse_min_sec(value)
                        elif idx == 1:             # m
                            res.second, res.microsecond = _parsems(value_repr)

                        i += 1
                        # We don't need to advance the tokens here because the
                        # i == len_l call indicates that we're looking at all
                        # the tokens already.

                    elif i+2 < len_l and l[i+1] == ':':
                        # HH:MM[:SS[.ss]]
                        res.hour = int(value)
                        value = float(l[i+2])
                        (res.minute, res.second) = _parse_min_sec(value)

                        if i+3 < len_l and l[i+3] == ':':
                            res.second, res.microsecond = _parsems(l[i+4])
                            i += 2

                        i += 3

                    elif i+1 < len_l and l[i+1] in ('-', '/', '.'):
                        sep = l[i+1]
                        ymd.append(value_repr)

                        if i+2 < len_l and not info.jump(l[i+2]):
                            try:
                                # 01-01[-01]
                                ymd.append(l[i+2])
                            except ValueError:
                                # 01-Jan[-01]
                                value = info.month(l[i+2])

                                if value is not None:
                                    ymd.append(value, 'M')
                                else:
                                    raise InvalidDatetimeError(timestr)

                            if i+3 < len_l and l[i+3] == sep:
                                # We have three members
                                value = info.month(l[i+4])

                                if value is not None:
                                    ymd.append(value, 'M')
                                else:
                                    ymd.append(l[i+4])
                                i += 2

                            i += 3
                        else:
                            i += 2

                    elif i+1 >= len_l or info.jump(l[i+1]):
                        if i+2 < len_l and info.ampm(l[i+2]) is not None:
                            # 12 am
                            hour = int(value)
                            res.hour = _adjust_ampm(hour, info.ampm(l[i+2]))
                            i += 1
                        else:
                            # Year, month or day
                            ymd.append(value)
                        i += 2

                    elif info.ampm(l[i+1]) is not None:
                        # 12am
                        hour = int(value)
                        res.hour = _adjust_ampm(hour, info.ampm(l[i+1]))
                        i += 2

                    elif not fuzzy:
                        raise InvalidDatetimeError(timestr)
                    else:
                        i += 1

                # Check weekday
                elif info.weekday(l[i]) is not None:
                    value = info.weekday(l[i])
                    res.weekday = value
                    i += 1

                # Check month name
                elif info.month(l[i]) is not None:
                    value = info.month(l[i])
                    ymd.append(value, 'M')

                    if i+1 < len_l:
                        if l[i+1] in ('-', '/'):
                            # Jan-01[-99]
                            sep = l[i+1]
                            ymd.append(l[i+2])

                            if i+3 < len_l and l[i+3] == sep:
                                # Jan-01-99
                                ymd.append(l[i+4])
                                i += 5
                            else:
                                i += 3

                        elif (i+4 < len_l and l[i+1] == l[i+3] == ' '
                              and info.pertain(l[i+2])):
                            # Jan of 01
                            # In this case, 01 is clearly year
                            try:
                                value = int(l[i+4])
                            except ValueError:
                                # Wrong guess
                                pass
                                # TODO: not hit in tests
                            else:
                                # Convert it here to become unambiguous
                                ymd.append(str(info.convertyear(value)), 'Y')
                            i += 5

                        else:
                            i += 1
                    else:
                        i += 1

                # Check am/pm
                elif info.ampm(l[i]) is not None:
                    value = info.ampm(l[i])
                    val_is_ampm = _ampm_validity(res.hour, res.ampm, fuzzy)

                    if val_is_ampm:
                        res.hour = _adjust_ampm(res.hour, value)
                        res.ampm = value

                    elif fuzzy:
                        skipped_idxs.add(i)

                    i += 1

                # Check for a timezone name
                elif (res.hour is not None and len(l[i]) <= 5
                    and res.tzname is None and res.tzoffset is None
                    and all(x in string.ascii_uppercase for x in l[i])):
                    res.tzname = l[i]
                    res.tzoffset = info.tzoffset(res.tzname)

                    # Check for something like GMT+3, or BRST+3. Notice
                    # that it doesn't mean "I am 3 hours after GMT", but
                    # "my time +3 is GMT". If found, we reverse the
                    # logic so that timezone parsing code will get it
                    # right.
                    if i+1 < len_l and l[i+1] in ('+', '-'):
                        l[i+1] = ('+', '-')[l[i+1] == '+']
                        res.tzoffset = None
                        if info.utczone(res.tzname):
                            # With something like GMT+3, the timezone
                            # is *not* GMT.
                            res.tzname = None

                    i += 1

                # Check for a numbered timezone
                elif res.hour is not None and l[i] in ('+', '-'):
                    signal = (-1, 1)[l[i] == '+']
                    len_li = len(l[i+1])

                    if len_li == 4:
                        # -0300
                        res.tzoffset = int(l[i+1][:2])*3600+int(l[i+1][2:])*60
                    elif i+2 < len_l and l[i+2] == ':':
                        # -03:00
                        res.tzoffset = int(l[i+1])*3600+int(l[i+3])*60
                        i += 2
                    elif len_li <= 2:
                        # -[0]3
                        res.tzoffset = int(l[i+1][:2])*3600
                    else:
                        raise InvalidDatetimeError(timestr)
                    i += 2

                    res.tzoffset *= signal

                    # Look for a timezone name between parenthesis
                    if (i+3 < len_l and
                        info.jump(l[i]) and l[i+1] == '(' and l[i+3] == ')' and
                        3 <= len(l[i+2]) <= 5 and
                        all(x in string.ascii_uppercase for x in l[i+2])):
                        # -0300 (BRST)
                        res.tzname = l[i+2]
                        i += 4

                # Check jumps
                elif not (info.jump(l[i]) or fuzzy):
                    raise InvalidDatetimeError(timestr)

                else:
                    skipped_idxs.add(i)
                    i += 1

            # Process year/month/day
            year, month, day = ymd.resolve_ymd(yearfirst, dayfirst)
            if year is not None:
                res.year = year
                res.century_specified = ymd.century_specified

            if month is not None:
                res.month = month

            if day is not None:
                res.day = day

        except (IndexError, ValueError, AssertionError):
            return None, None

        if not info.validate(res):
            return None, None

        if fuzzy_with_tokens:
            skipped_tokens = _recombine_skipped(l, skipped_idxs)
            return res, tuple(skipped_tokens)
        else:
            return res, None
