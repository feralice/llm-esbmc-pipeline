class CanutilsLogReader:
    def __iter__(self):
        for line in self.file:

            # skip empty lines
            temp = line.strip()
            if not temp:
                continue

            timestamp, channel, frame = temp.split()
            timestamp = float(timestamp[1:-1])
            canId, data = frame.split("#")
            if channel.isdigit():
                channel = int(channel)

            isExtended = len(canId) > 3
            canId = int(canId, 16)

            if data and data[0].lower() == "r":
                isRemoteFrame = True
                if len(data) > 1:
                    dlc = int(data[1:])
                else:
                    dlc = 0
            else:
                isRemoteFrame = False

                dlc = len(data) // 2
                dataBin = bytearray()
                for i in range(0, len(data), 2):
                    dataBin.append(int(data[i : (i + 2)], 16))

            if canId & CAN_ERR_FLAG and canId & CAN_ERR_BUSERROR:
                msg = Message(timestamp=timestamp, is_error_frame=True)
            else:
                msg = Message(
                    timestamp=timestamp,
                    arbitration_id=canId & 0x1FFFFFFF,
                    is_extended_id=isExtended,
                    is_remote_frame=isRemoteFrame,
                    dlc=dlc,
                    data=dataBin,
                    channel=channel,
                )
            yield msg

        self.stop()
