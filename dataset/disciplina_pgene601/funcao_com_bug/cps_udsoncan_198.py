class Client:
    def send_request(self, request: Request, timeout: int = -1) -> Optional[Response]:
        if request.service is None:
            raise ValueError("REquest has no service")

        if timeout < 0:
            # Timeout not provided by user: defaults to Client request_timeout value
            overall_timeout = self.config['request_timeout']
            p2 = self.config['p2_timeout'] if self.session_timing['p2_server_max'] is None else self.session_timing['p2_server_max']
            if overall_timeout is not None:
                single_request_timeout = min(overall_timeout, p2)
            else:
                single_request_timeout = p2
        else:
            overall_timeout = timeout
            single_request_timeout = timeout
        respect_overall_timeout = True
        if overall_timeout is None:
            respect_overall_timeout = False
        using_p2_star = False  # Will switch to true when Nrc 0x78 will be received the first time.

        self.conn.empty_rxqueue()
        self.logger.debug("Sending request to server")
        override_suppress_positive_response = False
        if self.suppress_positive_response.enabled == True and request.service.use_subfunction():
            payload = request.get_payload(suppress_positive_response=True)
            override_suppress_positive_response = True
        else:
            payload = request.get_payload()

        if self.payload_override.enabled:
            payload = self.payload_override.get_overrided_payload(payload)

        if self.suppress_positive_response.enabled and not request.service.use_subfunction():
            self.logger.warning('SuppressPositiveResponse cannot be used for service %s. Ignoring' % (request.service.get_name()))

        self.conn.send(payload)

        spr_used = request.suppress_positive_response or override_suppress_positive_response
        wait_nrc = self.suppress_positive_response.enabled and self.suppress_positive_response.wait_nrc

        if spr_used and not wait_nrc:
            return None

        done_receiving = False
        if respect_overall_timeout:
            overall_timeout_time = time.time() + overall_timeout

        timed_out = False
        while not done_receiving and not timed_out:
            done_receiving = True
            self.logger.debug("Waiting for server response")

            try:
                if not respect_overall_timeout or (respect_overall_timeout and time.time() + single_request_timeout < overall_timeout_time):
                    timeout_type_used = 'single_request'
                    timeout_value = single_request_timeout
                else:
                    timeout_type_used = 'overall'
                    timeout_value = max(overall_timeout_time - time.time(), 0)

                recv_payload = self.conn.wait_frame(timeout=timeout_value, exception=True)
            except TimeoutException:
                if timeout_type_used == 'single_request':
                    timeout_name_to_report = 'P2* timeout' if using_p2_star else 'P2 timeout'
                elif timeout_type_used == 'overall':
                    timeout_name_to_report = 'Global request timeout'
                else:  # Shouldn't go here.
                    timeout_name_to_report = 'Timeout'
                timed_out = True

            except Exception as e:
                raise e

            if timed_out or recv_payload is None:
                if spr_used:
                    return None
                raise TimeoutException('Did not receive response in time. %s time has expired (timeout=%.3f sec)' %
                                       (timeout_name_to_report, timeout_value))

            response = Response.from_payload(recv_payload)
            self.last_response = response
            self.logger.debug("Received response from server")

            if not response.valid:
                raise InvalidResponseException(response)

            assert response.service is not None
            assert response.code is not None

            if response.service.response_id() != request.service.response_id():
                msg = "Response gotten from server has a service ID different than the request service ID. Received=0x%02x, Expected=0x%02x" % (
                    response.service.response_id(), request.service.response_id())
                raise UnexpectedResponseException(response, msg)

            if not response.positive:
                try:
                    if not Response.Code.is_supported_by_standard(response.code, self.config['standard_version']):
                        self.logger.warning('Given response code "%s" (0x%02x) is not supported byt the UDS standard version that the clients s enforcing (%s)' % (
                            response.code_name,
                            response.code,
                            self.config['standard_version']))
                except ValueError:
                    self.logger.warning('Unkown response code "%s" (0x%02x)', response.code_name, response.code)

                if not request.service.is_supported_negative_response(response.code):
                    self.logger.warning('Given response code "%s" (0x%02x) is not a supported negative response code according to UDS standard.' % (
                        response.code_name, response.code))

                if response.code == Response.Code.RequestCorrectlyReceived_ResponsePending:
                    done_receiving = False
                    if not using_p2_star:
                        # Received a 0x78 NRC: timeout is now set to P2*
                        p2_star = self.config['p2_star_timeout'] if self.session_timing['p2_star_server_max'] is None else self.session_timing['p2_star_server_max']
                        single_request_timeout = p2_star
                        using_p2_star = True
                        self.logger.debug("Server requested to wait with response code %s (0x%02x), single request timeout is now set to P2* (%.3f seconds)" %
                                          (response.code_name, response.code, single_request_timeout))
                else:
                    raise NegativeResponseException(response)

        assert response.service is not None
        self.logger.info('Received positive response for service %s (0x%02x) from server.' %
                         (response.service.get_name(), response.service.request_id()))

        response.original_request = request

        if spr_used:
            return None

        return response
