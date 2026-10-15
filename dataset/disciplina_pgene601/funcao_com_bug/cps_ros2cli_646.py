class ListVerb:
    def main(self, *, args):  # noqa: D102
        with NodeStrategy(args) as node:
            node_names = get_node_names(
                node=node, include_hidden_nodes=args.include_hidden_nodes)

        node_name = get_absolute_node_name(args.node_name)
        if node_name:
            if node_name not in [n.full_name for n in node_names]:
                return 'Node not found'
            node_names = [
                n for n in node_names if node_name == n.full_name]

        regex_filter = getattr(args, 'filter')
        if regex_filter is not None:
            regex_filter = re.compile(regex_filter[0])

        with DirectNode(args) as node:
            service_names = get_service_names(
                node=node, include_hidden_services=args.include_hidden_nodes)

            clients = {}
            futures = {}
            # create clients for nodes which have the service
            for node_name in node_names:
                service_name = f'{node_name.full_name}/list_parameters'
                if service_name in service_names:
                    client = node.create_client(ListParameters, service_name)
                    clients[node_name] = client

            # wait until all clients have been called
            while True:
                for node_name in [
                    n for n in clients.keys() if n not in futures
                ]:
                    # call as soon as ready
                    client = clients[node_name]
                    if client.service_is_ready():
                        request = ListParameters.Request()
                        for prefix in args.param_prefixes:
                            request.prefixes.append(prefix)
                        future = client.call_async(request)
                        futures[node_name] = future

                if len(futures) == len(clients):
                    break
                rclpy.spin_once(node, timeout_sec=1.0)

            # wait for all responses
            for future in futures.values():
                rclpy.spin_until_future_complete(node, future, timeout_sec=1.0)

            # print responses
            for node_name in sorted(futures.keys()):
                future = futures[node_name]
                if future.result() is None:
                    e = future.exception()
                    print(
                        'Exception while calling service of node '
                        f"'{node_name.full_name}': {e}", file=sys.stderr)
                response = future.result()
                sorted_names = sorted(response.result.names)
                if regex_filter is not None:
                    sorted_names = [name for name in sorted_names if regex_filter.match(name)]
                if not args.node_name and sorted_names:
                    print(f'{node_name.full_name}:')
                # get descriptors for the node if needs to print parameter type
                name_to_type_map = {}
                if args.param_type is True:
                    resp = call_describe_parameters(
                        node=node, node_name=node_name.full_name,
                        parameter_names=sorted_names)
                    for descriptor in resp.descriptors:
                        name_to_type_map[descriptor.name] = get_parameter_type_string(
                            descriptor.type)

                for name in sorted_names:
                    if args.param_type is True:
                        param_type_str = name_to_type_map[name]
                        print(f'  {name} (type: {param_type_str})')
                    else:
                        print(f'  {name}')
