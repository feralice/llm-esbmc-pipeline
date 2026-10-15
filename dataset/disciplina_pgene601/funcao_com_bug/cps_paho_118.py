class Client:
    def _host_matches_cert(self, host, cert_host):
        if cert_host[0:2] == "*.":
            if cert_host.count("*") != 1:
                return False

            host_match = host.split(".", 1)[1]
            cert_match = cert_host.split(".", 1)[1]
            if host_match == cert_match:
                return True
            else:
                return False
        else:
            if host == cert_host:
                return True
            else:
                return False
