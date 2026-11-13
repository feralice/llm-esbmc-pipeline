# DESCARTADO em 13/11: o repositório está arquivado e o README diz "This project is deprecated". A issue não pôde ser criada (GitHub: Repository was archived so is read-only). Mantido só como registro.
# RASCUNHO. Não foi postado. Repositório: https://github.com/aws-samples/bedrock-access-gateway
# Rótulo do modelo do repositório: bug. Texto em inglês, para colar na issue depois que a Fernanda revisar.

**Title:** Malformed image URL such as `http://[::1` returns HTTP 500 instead of 400

**Describe the bug**

`_validate_url` in `src/api/image_url.py` calls `urlparse(url)` without a `try`. For some malformed URLs, `urlparse` raises `ValueError`, which nothing catches, so the request fails with HTTP 500. The rest of the module already maps invalid input to HTTP 400 (for example the invalid port case, `except ValueError`, and the `requests.RequestException` handler in `_fetch_image`).

The URL is still rejected, so this does not weaken the SSRF checks. It is only the status code and the unhandled exception.

**Please complete the following information:**
- [x] Which API you used: /chat/completions with `stream: false`
- [ ] Which model you used: any model whose modalities include IMAGE (the check runs before the Bedrock call). I did not run a full request against Bedrock.

**To Reproduce**

A `user` message with an `image_url` part whose `url` is `http://[::1`, with `ENABLE_IMAGE_URL_FETCH` left at its default (true). The `url` field is a plain `str` in `schema.py`, so pydantic does not reject it earlier.

What I actually ran: the real `api.image_url.parse_image_url` behind a minimal FastAPI endpoint, using FastAPI's `TestClient`:

```
'http://[::1'  -> 500   (ValueError: Invalid IPv6 URL, not handled)
'ftp://x/'     -> 400
'http:///'     -> 400
```

The call chain I read in the code: `chat` -> `_invoke_bedrock` -> `_parse_request` (outside the `try` that starts after it) -> `_parse_content_parts` -> `_parse_image` -> `parse_image_url` -> `_fetch_image` -> `_validate_url`.

With `stream: true` the exception is caught in `chat_stream` and sent to the client as an error event carrying the raw message (`Invalid IPv6 URL`), so only the non-streaming request ends in a 500.

**Expected behavior**

HTTP 400 with a short message such as "Image url is not valid", like the other invalid URL cases.

**Additional context**

A possible fix, tested on a copy of `image_url.py` with the same endpoint (all three cases above return 400):

```python
    try:
        parsed = urlparse(url)
    except ValueError:
        raise HTTPException(status_code=400, detail="Image url is not valid")
```

Notes on how this was found and what was checked:
- It was flagged by an LLM-assisted analysis pipeline and then reproduced outside it, in CPython (3.12), with the code at commit `144c4bc`. The formal verifier used by that pipeline did not confirm it (its result for this case was inconclusive), so the evidence is the reproduction above and reading the code.
- Before #262, `requests.get` raised `requests.exceptions.InvalidURL` for the same input, also unhandled, so this is not a regression of that change.
- I searched open and closed issues and PRs for this and found nothing.
- I am happy to send a PR with the fix and a test if you prefer.
