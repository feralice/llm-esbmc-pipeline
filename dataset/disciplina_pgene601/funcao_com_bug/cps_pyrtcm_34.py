class RTCMMessage:
    def __str__(self) -> str:
        """
        Human readable representation.

        :return: human readable representation
        :rtype: str
        """

        # if MSM message and labelmsm flag is set,
        # label NSAT and NCELL group attributes with
        # corresponding satellite PRN and signal ID
        if self._labelmsm and "MSM" in RTCM_MSGIDS[self.identity]:
            sats = sat2prn(self)
            cells = cell2prn(self)
            is_msm = True
        else:
            is_msm = False

        stg = f"<RTCM({self.identity}, "
        for i, att in enumerate(self.__dict__):
            if att[0] != "_":  # only show public attributes
                val = self.__dict__[att]
                # escape all byte chars
                if isinstance(val, bytes):
                    val = escapeall(val)
                # label MSM NSAT and NCELL group attributes
                lbl = ""
                if is_msm:
                    aname = att2name(att)
                    if aname in ATT_NSAT:
                        prn = sats[att2idx(att)]
                        lbl = f"({prn})"
                    if aname in ATT_NCELL:
                        prn, sig = cells[att2idx(att)]
                        lbl = f"({prn},{sig})"

                stg += att + lbl + "=" + str(val)
                if i < len(self.__dict__) - 1:
                    stg += ", "
        if self._unknown:
            stg += ", Not_Yet_Implemented"
        stg += ")>"

        return stg
