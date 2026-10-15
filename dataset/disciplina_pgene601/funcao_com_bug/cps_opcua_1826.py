class UaProcessor:
    async def _process_message(self, typeid, requesthdr, seqhdr, body):
        if typeid in [
            ua.NodeId(ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary),
            ua.NodeId(ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary),
            ua.NodeId(ua.ObjectIds.ActivateSessionRequest_Encoding_DefaultBinary),
            ua.NodeId(ua.ObjectIds.FindServersRequest_Encoding_DefaultBinary),
            ua.NodeId(ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary),
            ua.NodeId(ua.ObjectIds.RegisterServerRequest_Encoding_DefaultBinary),
            ua.NodeId(ua.ObjectIds.RegisterServer2Request_Encoding_DefaultBinary),
        ]:
            # The connection is first created without a user being attached, and then during activation the
            user = None
        elif self.session is None:
            _logger.warning("Received a request of type %d without an existing session", typeid.Identifier)
            raise ua.uaerrors.BadUserAccessDenied
        else:
            user = self.session.user
            if self._connection.security_policy.permissions is not None:
                if self._connection.security_policy.permissions.check_validity(user, typeid, body) is False:
                    raise ua.uaerrors.BadUserAccessDenied

        self.session_last_activity = datetime.now(timezone.utc)

        if typeid == ua.NodeId(ua.ObjectIds.CreateSessionRequest_Encoding_DefaultBinary):
            _logger.info("Create session request (%s)", user)
            params = struct_from_binary(ua.CreateSessionParameters, body)
            # create the session on server
            self.session = self.iserver.create_session(self.name, external=True)
            # get a session creation result to send back
            sessiondata = await self.session.create_session(params, sockname=self.sockname)
            self._closing = False
            self._session_watchdog_task = asyncio.create_task(self._session_watchdog_loop())
            response = ua.CreateSessionResponse()
            response.Parameters = sessiondata
            response.Parameters.ServerCertificate = self._connection.security_policy.host_certificate
            if self._connection.security_policy.peer_certificate is None:
                data = params.ClientNonce
            else:
                data = self._connection.security_policy.peer_certificate + params.ClientNonce
            response.Parameters.ServerSignature.Signature = (
                self._connection.security_policy.asymmetric_cryptography.signature(data)
            )
            response.Parameters.ServerSignature.Algorithm = self._connection.security_policy.AsymmetricSignatureURI
            # _logger.info("sending create session response")
            self.send_response(requesthdr.RequestHandle, seqhdr, response)

        elif typeid == ua.NodeId(ua.ObjectIds.CloseSessionRequest_Encoding_DefaultBinary):
            _logger.info("Close session request (%s)", user)
            if self.session:
                deletesubs = ua.ua_binary.Primitives.Boolean.unpack(body)
                self._closing = True
                await self.session.close_session(deletesubs)
            else:
                _logger.info("Request to close non-existing session (%s)", user)

            response = ua.CloseSessionResponse()
            _logger.info("sending close session response (%s)", user)
            self.send_response(requesthdr.RequestHandle, seqhdr, response)

        elif typeid == ua.NodeId(ua.ObjectIds.ActivateSessionRequest_Encoding_DefaultBinary):
            _logger.info("Activate session request (%s)", user)
            params = struct_from_binary(ua.ActivateSessionParameters, body)
            if not self.session:
                _logger.info("request to activate non-existing session (%s)", user)
                raise ServiceError(ua.StatusCodes.BadSessionIdInvalid)
            if self._connection.security_policy.host_certificate is None:
                data = self.session.nonce
            else:
                data = self._connection.security_policy.host_certificate + self.session.nonce
            self._connection.security_policy.asymmetric_cryptography.verify(data, params.ClientSignature.Signature)
            result = self.session.activate_session(params, self._connection.security_policy.peer_certificate)
            response = ua.ActivateSessionResponse()
            response.Parameters = result
            # _logger.info("sending read response")
            self.send_response(requesthdr.RequestHandle, seqhdr, response)
        elif typeid == ua.NodeId(ua.ObjectIds.GetEndpointsRequest_Encoding_DefaultBinary):
            _logger.info("get endpoints request (%s)", user)
            params = struct_from_binary(ua.GetEndpointsParameters, body)
            endpoints = await self.iserver.get_endpoints(params, sockname=self.sockname)
            response = ua.GetEndpointsResponse()
            response.Endpoints = endpoints
            # _logger.info("sending get endpoints response")
            self.send_response(requesthdr.RequestHandle, seqhdr, response)

        elif typeid == ua.NodeId(ua.ObjectIds.FindServersRequest_Encoding_DefaultBinary):
            _logger.info("find servers request (%s)", user)
            params = struct_from_binary(ua.FindServersParameters, body)
            servers = self.iserver.find_servers(params, sockname=self.sockname)
            response = ua.FindServersResponse()
            response.Servers = servers
            # _logger.info("sending find servers response")
            self.send_response(requesthdr.RequestHandle, seqhdr, response)

        elif typeid == ua.NodeId(ua.ObjectIds.RegisterServerRequest_Encoding_DefaultBinary):
            _logger.info("register server request %s", user)
            serv = struct_from_binary(ua.RegisteredServer, body)
            self.iserver.register_server(serv)
            response = ua.RegisterServerResponse()
            # _logger.info("sending register server response")
            self.send_response(requesthdr.RequestHandle, seqhdr, response)

        elif typeid == ua.NodeId(ua.ObjectIds.RegisterServer2Request_Encoding_DefaultBinary):
            _logger.info("register server 2 request %s", user)
            params = struct_from_binary(ua.RegisterServer2Parameters, body)
            results = self.iserver.register_server2(params)
            response = ua.RegisterServer2Response()
            response.ConfigurationResults = results
            # _logger.info("sending register server 2 response")
            self.send_response(requesthdr.RequestHandle, seqhdr, response)
        elif typeid == ua.NodeId(ua.ObjectIds.CloseSecureChannelRequest_Encoding_DefaultBinary):
            _logger.info("close secure channel request (%s)", user)
            self._connection.close()
            response = ua.CloseSecureChannelResponse()
            self.send_response(requesthdr.RequestHandle, seqhdr, response)
            return False
        else:
            # All services that require an active session
            if not self.session:
                _logger.info("Request service that need a session (%s)", user)
                raise ServiceError(ua.StatusCodes.BadSessionIdInvalid)
            if not self.session.is_activated():
                _logger.info("Request service that needs a activated session (%s)", user)
                raise ServiceError(ua.StatusCodes.BadSessionNotActivated)

            if typeid == ua.NodeId(ua.ObjectIds.ReadRequest_Encoding_DefaultBinary):
                _logger.info("Read request (%s)", user)
                params = struct_from_binary(ua.ReadParameters, body)
                results = await self.session.read(params)
                response = ua.ReadResponse()
                response.Results = results
                # _logger.info("sending read response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.WriteRequest_Encoding_DefaultBinary):
                _logger.info("Write request (%s)", user)
                params = struct_from_binary(ua.WriteParameters, body)
                results = await self.session.write(params)
                response = ua.WriteResponse()
                response.Results = results
                # _logger.info("sending write response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.BrowseRequest_Encoding_DefaultBinary):
                _logger.info("Browse request (%s)", user)
                params = struct_from_binary(ua.BrowseParameters, body)
                results = await self.session.browse(params)
                response = ua.BrowseResponse()
                response.Results = results
                # _logger.info("sending browse response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.TranslateBrowsePathsToNodeIdsRequest_Encoding_DefaultBinary):
                _logger.info("translate browsepaths to nodeids request (%s)", user)
                params = struct_from_binary(ua.TranslateBrowsePathsToNodeIdsParameters, body)
                paths = await self.session.translate_browsepaths_to_nodeids(params.BrowsePaths)
                response = ua.TranslateBrowsePathsToNodeIdsResponse()
                response.Results = paths
                # _logger.info("sending translate browsepaths to nodeids response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.AddNodesRequest_Encoding_DefaultBinary):
                _logger.info("add nodes request (%s)", user)
                params = struct_from_binary(ua.AddNodesParameters, body)
                results = await self.session.add_nodes(params.NodesToAdd)
                response = ua.AddNodesResponse()
                response.Results = results
                # _logger.info("sending add node response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.DeleteNodesRequest_Encoding_DefaultBinary):
                _logger.info("delete nodes request (%s)", user)
                params = struct_from_binary(ua.DeleteNodesParameters, body)
                results = await self.session.delete_nodes(params)
                response = ua.DeleteNodesResponse()
                response.Results = results
                # _logger.info("sending delete node response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.AddReferencesRequest_Encoding_DefaultBinary):
                _logger.info("add references request (%s)", user)
                params = struct_from_binary(ua.AddReferencesParameters, body)
                results = await self.session.add_references(params.ReferencesToAdd)
                response = ua.AddReferencesResponse()
                response.Results = results
                # _logger.info("sending add references response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.DeleteReferencesRequest_Encoding_DefaultBinary):
                _logger.info("delete references request (%s)", user)
                params = struct_from_binary(ua.DeleteReferencesParameters, body)
                results = await self.session.delete_references(params.ReferencesToDelete)
                response = ua.DeleteReferencesResponse()
                response.Parameters.Results = results
                # _logger.info("sending delete references response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.CreateSubscriptionRequest_Encoding_DefaultBinary):
                _logger.info("create subscription request (%s)", user)
                params = struct_from_binary(ua.CreateSubscriptionParameters, body)
                result = await self.session.create_subscription(
                    params, self.forward_publish_response, request_callback=self.get_publish_request
                )
                response = ua.CreateSubscriptionResponse()
                response.Parameters = result
                # _logger.info("sending create subscription response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.ModifySubscriptionRequest_Encoding_DefaultBinary):
                _logger.info("modify subscription request")
                params = struct_from_binary(ua.ModifySubscriptionParameters, body)

                result = self.session.modify_subscription(params)

                response = ua.ModifySubscriptionResponse()
                response.Parameters = result

                # _logger.info("sending modify subscription response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.DeleteSubscriptionsRequest_Encoding_DefaultBinary):
                _logger.info("delete subscriptions request (%s)", user)
                params = struct_from_binary(ua.DeleteSubscriptionsParameters, body)
                results = await self.session.delete_subscriptions(params.SubscriptionIds)
                response = ua.DeleteSubscriptionsResponse()
                response.Results = results
                # _logger.info("sending delete subscription response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.CreateMonitoredItemsRequest_Encoding_DefaultBinary):
                _logger.info("create monitored items request (%s)", user)
                params = struct_from_binary(ua.CreateMonitoredItemsParameters, body)
                results = await self.session.create_monitored_items(params)
                response = ua.CreateMonitoredItemsResponse()
                response.Results = results
                # _logger.info("sending create monitored items response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.ModifyMonitoredItemsRequest_Encoding_DefaultBinary):
                _logger.info("modify monitored items request (%s)", user)
                params = struct_from_binary(ua.ModifyMonitoredItemsParameters, body)
                results = await self.session.modify_monitored_items(params)
                response = ua.ModifyMonitoredItemsResponse()
                response.Results = results
                # _logger.info("sending modify monitored items response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.DeleteMonitoredItemsRequest_Encoding_DefaultBinary):
                _logger.info("delete monitored items request (%s)", user)
                params = struct_from_binary(ua.DeleteMonitoredItemsParameters, body)
                results = await self.session.delete_monitored_items(params)
                response = ua.DeleteMonitoredItemsResponse()
                response.Results = results
                # _logger.info("sending delete monitored items response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.HistoryReadRequest_Encoding_DefaultBinary):
                _logger.info("history read request (%s)", user)
                params = struct_from_binary(ua.HistoryReadParameters, body)
                results = await self.session.history_read(params)
                response = ua.HistoryReadResponse()
                response.Results = results
                # _logger.info("sending history read response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.RegisterNodesRequest_Encoding_DefaultBinary):
                _logger.info("register nodes request (%s)", user)
                params = struct_from_binary(ua.RegisterNodesParameters, body)
                _logger.info("Node registration not implemented")
                response = ua.RegisterNodesResponse()
                response.Parameters.RegisteredNodeIds = params.NodesToRegister
                # _logger.info("sending register nodes response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.UnregisterNodesRequest_Encoding_DefaultBinary):
                _logger.info("unregister nodes request (%s)", user)
                params = struct_from_binary(ua.UnregisterNodesParameters, body)
                response = ua.UnregisterNodesResponse()
                # _logger.info("sending unregister nodes response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.PublishRequest_Encoding_DefaultBinary):
                _logger.debug("publish request (%s)", user)
                if not self.session:
                    return False
                params = struct_from_binary(ua.PublishParameters, body)
                self.session.publish(params.SubscriptionAcknowledgements)
                data = PublishRequestData(requesthdr=requesthdr, seqhdr=seqhdr)
                # If there is an enqueued publish results callback, try to call it immediately
                while self._publish_results_subs:
                    subscription_id = next(iter(self._publish_results_subs))
                    self._publish_results_subs.pop(subscription_id)
                    sub = self.session.subscription_service.subscriptions.get(subscription_id)
                    if sub is None:
                        # subscription is no longer active
                        continue
                    if await sub.publish_results(data):
                        # publish request has been consumed
                        break
                else:
                    # Store the Publish Request (will be used to send publish answers from server)
                    self._publish_requests.append(data)

            elif typeid == ua.NodeId(ua.ObjectIds.RepublishRequest_Encoding_DefaultBinary):
                _logger.info("re-publish request (%s)", user)
                params = struct_from_binary(ua.RepublishParameters, body)
                msg = self.session.republish(params)
                response = ua.RepublishResponse()
                response.NotificationMessage = msg
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.CallRequest_Encoding_DefaultBinary):
                _logger.info("call request (%s)", user)
                params = struct_from_binary(ua.CallParameters, body)
                results = await self.session.call(params.MethodsToCall)
                response = ua.CallResponse()
                response.Results = results
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.SetMonitoringModeRequest_Encoding_DefaultBinary):
                _logger.info("set monitoring mode request (%s)", user)
                params = struct_from_binary(ua.SetMonitoringModeParameters, body)
                # FIXME: Implement SetMonitoringMode
                # For now send dummy results to keep clients happy
                response = ua.SetMonitoringModeResponse()
                results = ua.SetMonitoringModeResult()
                ids = params.MonitoredItemIds
                statuses = [ua.StatusCode(ua.StatusCodes.Good) for node_id in ids]
                results.Results = statuses
                response.Parameters = results
                _logger.info("sending set monitoring mode response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            elif typeid == ua.NodeId(ua.ObjectIds.SetPublishingModeRequest_Encoding_DefaultBinary):
                _logger.info("set publishing mode request (%s)", user)
                params = struct_from_binary(ua.SetPublishingModeParameters, body)
                # FIXME: Implement SetPublishingMode
                # For now send dummy results to keep clients happy
                response = ua.SetPublishingModeResponse()
                results = ua.SetPublishingModeResult()
                ids = params.SubscriptionIds
                statuses = [ua.StatusCode(ua.StatusCodes.Good) for node_id in ids]
                results.Results = statuses
                response.Parameters = results
                _logger.info("sending set publishing mode response")
                self.send_response(requesthdr.RequestHandle, seqhdr, response)

            else:
                _logger.warning("Unknown message received %s (%s)", typeid, user)
                raise ServiceError(ua.StatusCodes.BadServiceUnsupported)

        return True
