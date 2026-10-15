class ASCReader:
    def __iter__(self) -> Generator[Message, None, None]:
        self._extract_header()

        for _line in self.file:
            line = _line.strip()

            if trigger_match := ASC_TRIGGER_REGEX.match(line):
                datetime_str = trigger_match.group("datetime_string")
                self.start_time = (
                    0.0
                    if self.relative_timestamp
                    else self._datetime_to_timestamp(datetime_str)
                )
                continue

            if not ASC_MESSAGE_REGEX.match(line):
                # line might be a comment, chip status,
                # J1939 message or some other unsupported event
                continue

            msg_kwargs: Dict[str, Union[float, bool, int]] = {}
            try:
                _timestamp, channel, rest_of_message = line.split(None, 2)
                timestamp = float(_timestamp) + self.start_time
                msg_kwargs["timestamp"] = timestamp
                if channel == "CANFD":
                    msg_kwargs["is_fd"] = True
                elif channel.isdigit():
                    # See ASCWriter
                    msg_kwargs["channel"] = int(channel) - 1
                else:
                    # Not a CAN message. Possible values include "statistic", J1939TP
                    continue
            except ValueError:
                # Some other unprocessed or unknown format
                continue

            if "is_fd" not in msg_kwargs:
                msg = self._process_classic_can_frame(rest_of_message, msg_kwargs)
            else:
                msg = self._process_fd_can_frame(rest_of_message, msg_kwargs)
            if msg is not None:
                yield msg

        self.stop()

    def _process_fd_can_frame(self, line: str, msg_kwargs: Dict[str, Any]) -> Message:
        channel, direction, rest_of_message = line.split(None, 2)
        # See ASCWriter
        msg_kwargs["channel"] = int(channel) - 1
        msg_kwargs["is_rx"] = direction == "Rx"

        # CAN FD error frame
        if rest_of_message.strip()[:10].lower() == "errorframe":
            # Error Frame
            # TODO: maybe use regex to parse BRS, ESI, etc?
            msg_kwargs["is_error_frame"] = True
        else:
            can_id_str, frame_name_or_brs, rest_of_message = rest_of_message.split(
                None, 2
            )

            if frame_name_or_brs.isdigit():
                brs = frame_name_or_brs
                esi, dlc_str, data_length_str, data = rest_of_message.split(None, 3)
            else:
                brs, esi, dlc_str, data_length_str, data = rest_of_message.split(
                    None, 4
                )

            self._extract_can_id(can_id_str, msg_kwargs)
            msg_kwargs["bitrate_switch"] = brs == "1"
            msg_kwargs["error_state_indicator"] = esi == "1"
            dlc = int(dlc_str, self._converted_base)
            data_length = int(data_length_str)
            if data_length == 0:
                # CAN remote Frame
                msg_kwargs["is_remote_frame"] = True
                msg_kwargs["dlc"] = dlc
            else:
                if dlc2len(dlc) != data_length:
                    logger.warning(
                        "DLC vs Data Length mismatch %d[%d] != %d",
                        dlc,
                        dlc2len(dlc),
                        data_length,
                    )
                msg_kwargs["dlc"] = data_length

            self._process_data_string(data, data_length, msg_kwargs)

        return Message(**msg_kwargs)
