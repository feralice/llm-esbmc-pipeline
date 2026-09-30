# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/boto/boto/blob/2.38.0/boto/s3/key.py#L768-L886
# smelly line(s) in the original file: 768
# smelly line(s) in this file: 8
# ids: pysmell_1821
# note: Python 2 era source, kept as found
def sender(http_conn, method, path, data, headers):
    # This function is called repeatedly for temporary retries
    # so we must be sure the file pointer is pointing at the
    # start of the data.
    if spos is not None and spos != fp.tell():
        fp.seek(spos)
    elif spos is None and self.read_from_stream:
        # if seek is not supported, and we've read from this
        # stream already, then we need to abort retries to
        # avoid setting bad data.
        raise provider.storage_data_error(
            'Cannot retry failed request. fp does not support seeking.')

    # If the caller explicitly specified host header, tell putrequest
    # not to add a second host header. Similarly for accept-encoding.
    skips = {}
    if boto.utils.find_matching_headers('host', headers):
      skips['skip_host'] = 1
    if boto.utils.find_matching_headers('accept-encoding', headers):
      skips['skip_accept_encoding'] = 1
    http_conn.putrequest(method, path, **skips)
    for key in headers:
        http_conn.putheader(key, headers[key])
    http_conn.endheaders()

    save_debug = self.bucket.connection.debug
    self.bucket.connection.debug = 0
    # If the debuglevel < 4 we don't want to show connection
    # payload, so turn off HTTP connection-level debug output (to
    # be restored below).
    # Use the getattr approach to allow this to work in AppEngine.
    if getattr(http_conn, 'debuglevel', 0) < 4:
        http_conn.set_debuglevel(0)

    data_len = 0
    if cb:
        if size:
            cb_size = size
        elif self.size:
            cb_size = self.size
        else:
            cb_size = 0
        if chunked_transfer and cb_size == 0:
            # For chunked Transfer, we call the cb for every 1MB
            # of data transferred, except when we know size.
            cb_count = (1024 * 1024) / self.BufferSize
        elif num_cb > 1:
            cb_count = int(
                math.ceil(cb_size / self.BufferSize / (num_cb - 1.0)))
        elif num_cb < 0:
            cb_count = -1
        else:
            cb_count = 0
        i = 0
        cb(data_len, cb_size)

    bytes_togo = size
    if bytes_togo and bytes_togo < self.BufferSize:
        chunk = fp.read(bytes_togo)
    else:
        chunk = fp.read(self.BufferSize)

    if not isinstance(chunk, bytes):
        chunk = chunk.encode('utf-8')

    if spos is None:
        # read at least something from a non-seekable fp.
        self.read_from_stream = True
    while chunk:
        chunk_len = len(chunk)
        data_len += chunk_len
        if chunked_transfer:
            http_conn.send('%x;\r\n' % chunk_len)
            http_conn.send(chunk)
            http_conn.send('\r\n')
        else:
            http_conn.send(chunk)
        for alg in digesters:
            digesters[alg].update(chunk)
        if bytes_togo:
            bytes_togo -= chunk_len
            if bytes_togo <= 0:
                break
        if cb:
            i += 1
            if i == cb_count or cb_count == -1:
                cb(data_len, cb_size)
                i = 0
        if bytes_togo and bytes_togo < self.BufferSize:
            chunk = fp.read(bytes_togo)
        else:
            chunk = fp.read(self.BufferSize)

        if not isinstance(chunk, bytes):
            chunk = chunk.encode('utf-8')

    self.size = data_len

    for alg in digesters:
        self.local_hashes[alg] = digesters[alg].digest()

    if chunked_transfer:
        http_conn.send('0\r\n')
            # http_conn.send("Content-MD5: %s\r\n" % self.base64md5)
        http_conn.send('\r\n')

    if cb and (cb_count <= 1 or i > 0) and data_len > 0:
        cb(data_len, cb_size)

    http_conn.set_debuglevel(save_debug)
    self.bucket.connection.debug = save_debug
    response = http_conn.getresponse()
    body = response.read()

    if not self.should_retry(response, chunked_transfer):
        raise provider.storage_response_error(
            response.status, response.reason, body)

    return response
