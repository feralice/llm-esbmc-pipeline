class GPS:
    def update(self):
        """Check for updated data from the GPS module and process it
        accordingly.  Returns True if new data was processed, and False if
        nothing new was received.
        """
        # Grab a sentence and check its data type to call the appropriate
        # parsing function.

        try:
            sentence = self._parse_sentence()
        except UnicodeError:
            return None
        if sentence is None:
            return False
        if self.debug:
            print(sentence)
        data_type, args = sentence
        data_type = bytes(data_type.upper(), "ascii")
        (talker, sentence_type) = _parse_talker(data_type)

        # Check for all currently known GNSS talkers
        # GA - Galileo
        # GB - BeiDou Systems
        # GI - NavIC
        # GL - GLONASS
        # GP - GPS
        # GQ - QZSS
        # GN - GNSS / More than one of the above
        if talker not in (b"GA", b"GB", b"GI", b"GL", b"GP", b"GQ", b"GN"):
            # It's not a known GNSS source of data
            # Assume it's a valid packet anyway
            return True

        result = True
        args = args.split(",")
        if sentence_type == b"GLL":  # Geographic position - Latitude/Longitude
            result = self._parse_gll(args)
        elif sentence_type == b"RMC":  # Minimum location info
            result = self._parse_rmc(args)
        elif sentence_type == b"GGA":  # 3D location fix
            result = self._parse_gga(args)
        elif sentence_type == b"GSV":  # Satellites in view
            result = self._parse_gsv(talker, args)
        elif sentence_type == b"GSA":  # GPS DOP and active satellites
            result = self._parse_gsa(talker, args)

        return result


def _parse_talker(data_type):
    # Split the data_type into talker and sentence_type
    if data_type[0] == b"P":  # Proprietary codes
        return (data_type[:1], data_type[1:])

    return (data_type[:2], data_type[2:])
