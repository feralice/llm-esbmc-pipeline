class MQTT:
    def connect(self, clean_session=True):
        """Initiates connection with the MQTT Broker.
        :param bool clean_session: Establishes a persistent session.
        """
        self._set_interface()
        if self._logger is not None:
            self._logger.debug('Creating new socket')
        self._sock = self._socket.socket()
        self._sock.settimeout(10)
        if self.port == 8883:
            try:
                if self._logger is not None:
                    self._logger.debug('Attempting to establish secure MQTT connection...')
                self._sock.connect((self.broker, self.port), TLS_MODE)
            except RuntimeError:
                raise MMQTTException("Invalid broker address defined.")
        else:
            if isinstance(self.broker, str):
                addr = self._socket.getaddrinfo(self.broker, self.port)[0][-1]
            else:
                addr = (self.broker, self.port)
            try:
                if self._logger is not None:
                    self._logger.debug('Attempting to establish insecure MQTT connection...')
                #self._sock.connect((self.broker, self.port), TCP_MODE)
                self._sock.connect(addr, TCP_MODE)
            except RuntimeError as e:
                raise MMQTTException("Invalid broker address defined.", e)

        # Fixed Header
        fixed_header = bytearray()
        fixed_header.append(0x10)

        # Variable Header
        var_header = MQTT_VAR_HEADER
        var_header[6] = clean_session << 1

        # Set up variable header and remaining_length
        remaining_length = 12 + len(self._client_id)
        if self._user is not None:
            remaining_length += 2 + len(self._user) + 2 + len(self._pass)
            var_header[6] |= 0xC0
        if self._keep_alive:
            assert self._keep_alive < MQTT_TOPIC_LENGTH_LIMIT
            var_header[7] |= self._keep_alive >> 8
            var_header[8] |= self._keep_alive & 0x00FF
        if self._lw_topic:
            remaining_length += 2 + len(self._lw_topic) + 2 + len(self._lw_msg)
            var_header[6] |= 0x4 | (self._lw_qos & 0x1) << 3 | (self._lw_qos & 0x2) << 3
            var_header[6] |= self._lw_retain << 5

        # Remaining length calculation
        large_rel_length = False
        if remaining_length > 0x7f:
            large_rel_length = True
            # Calculate Remaining Length [2.2.3]
            while remaining_length > 0:
                encoded_byte = remaining_length % 0x80
                remaining_length = remaining_length // 0x80
                # if there is more data to encode, set the top bit of the byte
                if remaining_length > 0:
                    encoded_byte |= 0x80
                fixed_header.append(encoded_byte)
        if large_rel_length:
            fixed_header.append(0x00)
        else:
            fixed_header.append(remaining_length)
            fixed_header.append(0x00)

        if self._logger is not None:
            self._logger.debug('Sending CONNECT to broker')
            self._logger.debug('Fixed Header: {}\nVariable Header: {}'.format(fixed_header,
                                                                              var_header))
        self._sock.write(fixed_header)
        self._sock.write(var_header)
        # [MQTT-3.1.3-4]
        self._send_str(self._client_id)
        if self._lw_topic:
            # [MQTT-3.1.3-11]
            self._send_str(self._lw_topic)
            self._send_str(self._lw_msg)
        if self._user is None:
            self._user = None
        else:
            self._send_str(self._user)
            self._send_str(self._pass)
        if self._logger is not None:
            self._logger.debug('Receiving CONNACK packet from broker')
        while True:
            op = self._wait_for_msg()
            if op == 32:
                rc = self._sock.read(3)
                assert rc[0] == 0x02
                if rc[2] != 0x00:
                    raise MMQTTException(CONNACK_ERRORS[rc[3]])
                self._is_connected = True
                result = rc[0] & 1
                if self.on_connect is not None:
                    self.on_connect(self, self._user_data, result, rc[2])
                return result
