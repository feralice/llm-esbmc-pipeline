class ASCReader:
    def __iter__(self):
        for line in self.file:
            logger.debug("ASCReader: parsing line: '%s'", line.splitlines()[0])

            temp = line.strip()
            if not temp or not temp[0].isdigit():
                continue
            (timestamp, channel, dummy) = temp.split(None, 2) # , frameType, dlc, frameData
            timestamp = float(timestamp)

            if dummy.strip()[0:10] == 'ErrorFrame':
                msg = Message(timestamp=timestamp, is_error_frame=True)
                yield msg

            elif not channel.isdigit() or dummy.strip()[0:10] == 'Statistic:':
                pass

            elif dummy[-1:].lower() == 'r':
                (can_id_str, _) = dummy.split(None, 1)
                (can_id_num, is_extended_id) = self._extract_can_id(can_id_str)
                msg = Message(timestamp=timestamp,
                              arbitration_id=can_id_num & CAN_ID_MASK,
                              extended_id=is_extended_id,
                              is_remote_frame=True)
                yield msg

            else:
                try:
                    # this only works if dlc > 0 and thus data is availabe
                    (can_id_str, _, _, dlc, data) = dummy.split(None, 4)
                except ValueError:
                    # but if not, we only want to get the stuff up to the dlc
                    (can_id_str, _, _, dlc      ) = dummy.split(None, 3)
                    # and we set data to an empty sequence manually
                    data = ''

                dlc = int(dlc)
                frame = bytearray()
                data = data.split()
                for byte in data[0:dlc]:
                    frame.append(int(byte, 16))

                (can_id_num, is_extended_id) = self._extract_can_id(can_id_str)

                msg = Message(
                            timestamp=timestamp,
                            arbitration_id=can_id_num & CAN_ID_MASK,
                            extended_id=is_extended_id,
                            is_remote_frame=False,
                            dlc=dlc,
                            data=frame)
                yield msg
