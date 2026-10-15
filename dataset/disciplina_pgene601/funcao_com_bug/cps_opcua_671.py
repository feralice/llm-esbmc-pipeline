def application_to_strings(app):
    result = [("Application URI", app.ApplicationUri)]
    optionals = [
        ("Product URI", app.ProductUri),
        ("Application Name", app.ApplicationName.to_string()),
        ("Application Type", str(app.ApplicationType)),
        ("Gateway Server URI", app.GatewayServerUri),
        ("Discovery Profile URI", app.DiscoveryProfileUri),
    ]
    for (n, v) in optionals:
        if v:
            result.append((n, v))
    for url in app.DiscoveryUrls:
        result.append(("Discovery URL", url))
    return result  # ['{}: {}'.format(n, v) for (n, v) in result]
