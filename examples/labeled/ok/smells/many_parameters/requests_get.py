# Extracted from requests/api.py — Requests HTTP library
# Source: requests project (Kenneth Reitz) / requests.get()
# Smell: many parameters — 8 parameters including timeout, verify, cert, stream, auth, proxies
def get(url: str, params=None, headers=None, auth=None, timeout=None,
        allow_redirects: bool = True, verify: bool = True, stream: bool = False) -> dict:
    return request("GET", url, params=params, headers=headers, auth=auth,
                   timeout=timeout, allow_redirects=allow_redirects,
                   verify=verify, stream=stream)

def request(method: str, url: str, **kwargs) -> dict:
    return {"method": method, "url": url, **kwargs}
