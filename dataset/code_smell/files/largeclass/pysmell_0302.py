# smell: LargeClass
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/tornadoweb/tornado/blob/v4.2.0/tornado/iostream.py#L110-L935
# smelly line(s) in the original file: 110
# smelly line(s) in this file: 8
# ids: pysmell_0302
# note: Python 2 era source, kept as found
class BaseIOStream(object):
    """A utility class to write to and read from a non-blocking file or socket.

    We support a non-blocking ``write()`` and a family of ``read_*()`` methods.
    All of the methods take an optional ``callback`` argument and return a
    `.Future` only if no callback is given.  When the operation completes,
    the callback will be run or the `.Future` will resolve with the data
    read (or ``None`` for ``write()``).  All outstanding ``Futures`` will
    resolve with a `StreamClosedError` when the stream is closed; users
    of the callback interface will be notified via
    `.BaseIOStream.set_close_callback` instead.

    When a stream is closed due to an error, the IOStream's ``error``
    attribute contains the exception object.

    Subclasses must implement `fileno`, `close_fd`, `write_to_fd`,
    `read_from_fd`, and optionally `get_fd_error`.
    """
    def __init__(self, io_loop=None, max_buffer_size=None,
                 read_chunk_size=None, max_write_buffer_size=None):
        """`BaseIOStream` constructor.

        :arg io_loop: The `.IOLoop` to use; defaults to `.IOLoop.current`.
                      Deprecated since Tornado 4.1.
        :arg max_buffer_size: Maximum amount of incoming data to buffer;
            defaults to 100MB.
        :arg read_chunk_size: Amount of data to read at one time from the
            underlying transport; defaults to 64KB.
        :arg max_write_buffer_size: Amount of outgoing data to buffer;
            defaults to unlimited.

        .. versionchanged:: 4.0
           Add the ``max_write_buffer_size`` parameter.  Changed default
           ``read_chunk_size`` to 64KB.
        """
        self.io_loop = io_loop or ioloop.IOLoop.current()
        self.max_buffer_size = max_buffer_size or 104857600
        # A chunk size that is too close to max_buffer_size can cause
        # spurious failures.
        self.read_chunk_size = min(read_chunk_size or 65536,
                                   self.max_buffer_size // 2)
        self.max_write_buffer_size = max_write_buffer_size
        self.error = None
        self._read_buffer = collections.deque()
        self._write_buffer = collections.deque()
        self._read_buffer_size = 0
        self._write_buffer_size = 0
        self._write_buffer_frozen = False
        self._read_delimiter = None
        self._read_regex = None
        self._read_max_bytes = None
        self._read_bytes = None
        self._read_partial = False
        self._read_until_close = False
        self._read_callback = None
        self._read_future = None
        self._streaming_callback = None
        self._write_callback = None
        self._write_future = None
        self._close_callback = None
        self._connect_callback = None
        self._connect_future = None
        # _ssl_connect_future should be defined in SSLIOStream
        # but it's here so we can clean it up in maybe_run_close_callback.
        # TODO: refactor that so subclasses can add additional futures
        # to be cancelled.
        self._ssl_connect_future = None
        self._connecting = False
        self._state = None
        self._pending_callbacks = 0
        self._closed = False

    def fileno(self):
        """Returns the file descriptor for this stream."""
        raise NotImplementedError()

    def close_fd(self):
        """Closes the file underlying this stream.

        ``close_fd`` is called by `BaseIOStream` and should not be called
        elsewhere; other users should call `close` instead.
        """
        raise NotImplementedError()

    def write_to_fd(self, data):
        """Attempts to write ``data`` to the underlying file.

        Returns the number of bytes written.
        """
        raise NotImplementedError()

    def read_from_fd(self):
        """Attempts to read from the underlying file.

        Returns ``None`` if there was nothing to read (the socket
        returned `~errno.EWOULDBLOCK` or equivalent), otherwise
        returns the data.  When possible, should return no more than
        ``self.read_chunk_size`` bytes at a time.
        """
        raise NotImplementedError()

    def get_fd_error(self):
        """Returns information about any error on the underlying file.

        This method is called after the `.IOLoop` has signaled an error on the
        file descriptor, and should return an Exception (such as `socket.error`
        with additional information, or None if no such information is
        available.
        """
        return None

    def read_until_regex(self, regex, callback=None, max_bytes=None):
        """Asynchronously read until we have matched the given regex.

        The result includes the data that matches the regex and anything
        that came before it.  If a callback is given, it will be run
        with the data as an argument; if not, this method returns a
        `.Future`.

        If ``max_bytes`` is not None, the connection will be closed
        if more than ``max_bytes`` bytes have been read and the regex is
        not satisfied.

        .. versionchanged:: 4.0
            Added the ``max_bytes`` argument.  The ``callback`` argument is
            now optional and a `.Future` will be returned if it is omitted.
        """
        future = self._set_read_callback(callback)
        self._read_regex = re.compile(regex)
        self._read_max_bytes = max_bytes
        try:
            self._try_inline_read()
        except UnsatisfiableReadError as e:
            # Handle this the same way as in _handle_events.
            gen_log.info("Unsatisfiable read, closing connection: %s" % e)
            self.close(exc_info=True)
            return future
        except:
            if future is not None:
                # Ensure that the future doesn't log an error because its
                # failure was never examined.
                future.add_done_callback(lambda f: f.exception())
            raise
        return future

    def read_until(self, delimiter, callback=None, max_bytes=None):
        """Asynchronously read until we have found the given delimiter.

        The result includes all the data read including the delimiter.
        If a callback is given, it will be run with the data as an argument;
        if not, this method returns a `.Future`.

        If ``max_bytes`` is not None, the connection will be closed
        if more than ``max_bytes`` bytes have been read and the delimiter
        is not found.

        .. versionchanged:: 4.0
            Added the ``max_bytes`` argument.  The ``callback`` argument is
            now optional and a `.Future` will be returned if it is omitted.
        """
        future = self._set_read_callback(callback)
        self._read_delimiter = delimiter
        self._read_max_bytes = max_bytes
        try:
            self._try_inline_read()
        except UnsatisfiableReadError as e:
            # Handle this the same way as in _handle_events.
            gen_log.info("Unsatisfiable read, closing connection: %s" % e)
            self.close(exc_info=True)
            return future
        except:
            if future is not None:
                future.add_done_callback(lambda f: f.exception())
            raise
        return future

    def read_bytes(self, num_bytes, callback=None, streaming_callback=None,
                   partial=False):
        """Asynchronously read a number of bytes.

        If a ``streaming_callback`` is given, it will be called with chunks
        of data as they become available, and the final result will be empty.
        Otherwise, the result is all the data that was read.
        If a callback is given, it will be run with the data as an argument;
        if not, this method returns a `.Future`.

        If ``partial`` is true, the callback is run as soon as we have
        any bytes to return (but never more than ``num_bytes``)

        .. versionchanged:: 4.0
            Added the ``partial`` argument.  The callback argument is now
            optional and a `.Future` will be returned if it is omitted.
        """
        future = self._set_read_callback(callback)
        assert isinstance(num_bytes, numbers.Integral)
        self._read_bytes = num_bytes
        self._read_partial = partial
        self._streaming_callback = stack_context.wrap(streaming_callback)
        try:
            self._try_inline_read()
        except:
            if future is not None:
                future.add_done_callback(lambda f: f.exception())
            raise
        return future

    def read_until_close(self, callback=None, streaming_callback=None):
        """Asynchronously reads all data from the socket until it is closed.

        If a ``streaming_callback`` is given, it will be called with chunks
        of data as they become available, and the final result will be empty.
        Otherwise, the result is all the data that was read.
        If a callback is given, it will be run with the data as an argument;
        if not, this method returns a `.Future`.

        Note that if a ``streaming_callback`` is used, data will be
        read from the socket as quickly as it becomes available; there
        is no way to apply backpressure or cancel the reads. If flow
        control or cancellation are desired, use a loop with
        `read_bytes(partial=True) <.read_bytes>` instead.

        .. versionchanged:: 4.0
            The callback argument is now optional and a `.Future` will
            be returned if it is omitted.

        """
        future = self._set_read_callback(callback)
        self._streaming_callback = stack_context.wrap(streaming_callback)
        if self.closed():
            if self._streaming_callback is not None:
                self._run_read_callback(self._read_buffer_size, True)
            self._run_read_callback(self._read_buffer_size, False)
            return future
        self._read_until_close = True
        try:
            self._try_inline_read()
        except:
            future.add_done_callback(lambda f: f.exception())
            raise
        return future

    def write(self, data, callback=None):
        """Asynchronously write the given data to this stream.

        If ``callback`` is given, we call it when all of the buffered write
        data has been successfully written to the stream. If there was
        previously buffered write data and an old write callback, that
        callback is simply overwritten with this new callback.

        If no ``callback`` is given, this method returns a `.Future` that
        resolves (with a result of ``None``) when the write has been
        completed.  If `write` is called again before that `.Future` has
        resolved, the previous future will be orphaned and will never resolve.

        .. versionchanged:: 4.0
            Now returns a `.Future` if no callback is given.
        """
        assert isinstance(data, bytes)
        self._check_closed()
        # We use bool(_write_buffer) as a proxy for write_buffer_size>0,
        # so never put empty strings in the buffer.
        if data:
            if (self.max_write_buffer_size is not None and
                    self._write_buffer_size + len(data) > self.max_write_buffer_size):
                raise StreamBufferFullError("Reached maximum write buffer size")
            # Break up large contiguous strings before inserting them in the
            # write buffer, so we don't have to recopy the entire thing
            # as we slice off pieces to send to the socket.
            WRITE_BUFFER_CHUNK_SIZE = 128 * 1024
            for i in range(0, len(data), WRITE_BUFFER_CHUNK_SIZE):
                self._write_buffer.append(data[i:i + WRITE_BUFFER_CHUNK_SIZE])
            self._write_buffer_size += len(data)
        if callback is not None:
            self._write_callback = stack_context.wrap(callback)
            future = None
        else:
            future = self._write_future = TracebackFuture()
            future.add_done_callback(lambda f: f.exception())
        if not self._connecting:
            self._handle_write()
            if self._write_buffer:
                self._add_io_state(self.io_loop.WRITE)
            self._maybe_add_error_listener()
        return future

    def set_close_callback(self, callback):
        """Call the given callback when the stream is closed.

        This is not necessary for applications that use the `.Future`
        interface; all outstanding ``Futures`` will resolve with a
        `StreamClosedError` when the stream is closed.
        """
        self._close_callback = stack_context.wrap(callback)
        self._maybe_add_error_listener()

    def close(self, exc_info=False):
        """Close this stream.

        If ``exc_info`` is true, set the ``error`` attribute to the current
        exception from `sys.exc_info` (or if ``exc_info`` is a tuple,
        use that instead of `sys.exc_info`).
        """
        if not self.closed():
            if exc_info:
                if not isinstance(exc_info, tuple):
                    exc_info = sys.exc_info()
                if any(exc_info):
                    self.error = exc_info[1]
            if self._read_until_close:
                if (self._streaming_callback is not None and
                        self._read_buffer_size):
                    self._run_read_callback(self._read_buffer_size, True)
                self._read_until_close = False
                self._run_read_callback(self._read_buffer_size, False)
            if self._state is not None:
                self.io_loop.remove_handler(self.fileno())
                self._state = None
            self.close_fd()
            self._closed = True
        self._maybe_run_close_callback()

    def _maybe_run_close_callback(self):
        # If there are pending callbacks, don't run the close callback
        # until they're done (see _maybe_add_error_handler)
        if self.closed() and self._pending_callbacks == 0:
            futures = []
            if self._read_future is not None:
                futures.append(self._read_future)
                self._read_future = None
            if self._write_future is not None:
                futures.append(self._write_future)
                self._write_future = None
            if self._connect_future is not None:
                futures.append(self._connect_future)
                self._connect_future = None
            if self._ssl_connect_future is not None:
                futures.append(self._ssl_connect_future)
                self._ssl_connect_future = None
            for future in futures:
                if self._is_connreset(self.error):
                    # Treat connection resets as closed connections so
                    # clients only have to catch one kind of exception
                    # to avoid logging.
                    future.set_exception(StreamClosedError())
                else:
                    future.set_exception(self.error or StreamClosedError())
            if self._close_callback is not None:
                cb = self._close_callback
                self._close_callback = None
                self._run_callback(cb)
            # Delete any unfinished callbacks to break up reference cycles.
            self._read_callback = self._write_callback = None
            # Clear the buffers so they can be cleared immediately even
            # if the IOStream object is kept alive by a reference cycle.
            # TODO: Clear the read buffer too; it currently breaks some tests.
            self._write_buffer = None

    def reading(self):
        """Returns true if we are currently reading from the stream."""
        return self._read_callback is not None or self._read_future is not None

    def writing(self):
        """Returns true if we are currently writing to the stream."""
        return bool(self._write_buffer)

    def closed(self):
        """Returns true if the stream has been closed."""
        return self._closed

    def set_nodelay(self, value):
        """Sets the no-delay flag for this stream.

        By default, data written to TCP streams may be held for a time
        to make the most efficient use of bandwidth (according to
        Nagle's algorithm).  The no-delay flag requests that data be
        written as soon as possible, even if doing so would consume
        additional bandwidth.

        This flag is currently defined only for TCP-based ``IOStreams``.

        .. versionadded:: 3.1
        """
        pass

    def _handle_events(self, fd, events):
        if self.closed():
            gen_log.warning("Got events for closed stream %s", fd)
            return
        try:
            if self._connecting:
                # Most IOLoops will report a write failed connect
                # with the WRITE event, but SelectIOLoop reports a
                # READ as well so we must check for connecting before
                # either.
                self._handle_connect()
            if self.closed():
                return
            if events & self.io_loop.READ:
                self._handle_read()
            if self.closed():
                return
            if events & self.io_loop.WRITE:
                self._handle_write()
            if self.closed():
                return
            if events & self.io_loop.ERROR:
                self.error = self.get_fd_error()
                # We may have queued up a user callback in _handle_read or
                # _handle_write, so don't close the IOStream until those
                # callbacks have had a chance to run.
                self.io_loop.add_callback(self.close)
                return
            state = self.io_loop.ERROR
            if self.reading():
                state |= self.io_loop.READ
            if self.writing():
                state |= self.io_loop.WRITE
            if state == self.io_loop.ERROR and self._read_buffer_size == 0:
                # If the connection is idle, listen for reads too so
                # we can tell if the connection is closed.  If there is
                # data in the read buffer we won't run the close callback
                # yet anyway, so we don't need to listen in this case.
                state |= self.io_loop.READ
            if state != self._state:
                assert self._state is not None, \
                    "shouldn't happen: _handle_events without self._state"
                self._state = state
                self.io_loop.update_handler(self.fileno(), self._state)
        except UnsatisfiableReadError as e:
            gen_log.info("Unsatisfiable read, closing connection: %s" % e)
            self.close(exc_info=True)
        except Exception:
            gen_log.error("Uncaught exception, closing connection.",
                          exc_info=True)
            self.close(exc_info=True)
            raise

    def _run_callback(self, callback, *args):
        def wrapper():
            self._pending_callbacks -= 1
            try:
                return callback(*args)
            except Exception:
                app_log.error("Uncaught exception, closing connection.",
                              exc_info=True)
                # Close the socket on an uncaught exception from a user callback
                # (It would eventually get closed when the socket object is
                # gc'd, but we don't want to rely on gc happening before we
                # run out of file descriptors)
                self.close(exc_info=True)
                # Re-raise the exception so that IOLoop.handle_callback_exception
                # can see it and log the error
                raise
            finally:
                self._maybe_add_error_listener()
        # We schedule callbacks to be run on the next IOLoop iteration
        # rather than running them directly for several reasons:
        # * Prevents unbounded stack growth when a callback calls an
        #   IOLoop operation that immediately runs another callback
        # * Provides a predictable execution context for e.g.
        #   non-reentrant mutexes
        # * Ensures that the try/except in wrapper() is run outside
        #   of the application's StackContexts
        with stack_context.NullContext():
            # stack_context was already captured in callback, we don't need to
            # capture it again for IOStream's wrapper.  This is especially
            # important if the callback was pre-wrapped before entry to
            # IOStream (as in HTTPConnection._header_callback), as we could
            # capture and leak the wrong context here.
            self._pending_callbacks += 1
            self.io_loop.add_callback(wrapper)

    def _read_to_buffer_loop(self):
        # This method is called from _handle_read and _try_inline_read.
        try:
            if self._read_bytes is not None:
                target_bytes = self._read_bytes
            elif self._read_max_bytes is not None:
                target_bytes = self._read_max_bytes
            elif self.reading():
                # For read_until without max_bytes, or
                # read_until_close, read as much as we can before
                # scanning for the delimiter.
                target_bytes = None
            else:
                target_bytes = 0
            next_find_pos = 0
            # Pretend to have a pending callback so that an EOF in
            # _read_to_buffer doesn't trigger an immediate close
            # callback.  At the end of this method we'll either
            # establish a real pending callback via
            # _read_from_buffer or run the close callback.
            #
            # We need two try statements here so that
            # pending_callbacks is decremented before the `except`
            # clause below (which calls `close` and does need to
            # trigger the callback)
            self._pending_callbacks += 1
            while not self.closed():
                # Read from the socket until we get EWOULDBLOCK or equivalent.
                # SSL sockets do some internal buffering, and if the data is
                # sitting in the SSL object's buffer select() and friends
                # can't see it; the only way to find out if it's there is to
                # try to read it.
                if self._read_to_buffer() == 0:
                    break

                self._run_streaming_callback()

                # If we've read all the bytes we can use, break out of
                # this loop.  We can't just call read_from_buffer here
                # because of subtle interactions with the
                # pending_callback and error_listener mechanisms.
                #
                # If we've reached target_bytes, we know we're done.
                if (target_bytes is not None and
                        self._read_buffer_size >= target_bytes):
                    break

                # Otherwise, we need to call the more expensive find_read_pos.
                # It's inefficient to do this on every read, so instead
                # do it on the first read and whenever the read buffer
                # size has doubled.
                if self._read_buffer_size >= next_find_pos:
                    pos = self._find_read_pos()
                    if pos is not None:
                        return pos
                    next_find_pos = self._read_buffer_size * 2
            return self._find_read_pos()
        finally:
            self._pending_callbacks -= 1

    def _handle_read(self):
        try:
            pos = self._read_to_buffer_loop()
        except UnsatisfiableReadError:
            raise
        except Exception:
            gen_log.warning("error on read", exc_info=True)
            self.close(exc_info=True)
            return
        if pos is not None:
            self._read_from_buffer(pos)
            return
        else:
            self._maybe_run_close_callback()

    def _set_read_callback(self, callback):
        assert self._read_callback is None, "Already reading"
        assert self._read_future is None, "Already reading"
        if callback is not None:
            self._read_callback = stack_context.wrap(callback)
        else:
            self._read_future = TracebackFuture()
        return self._read_future

    def _run_read_callback(self, size, streaming):
        if streaming:
            callback = self._streaming_callback
        else:
            callback = self._read_callback
            self._read_callback = self._streaming_callback = None
            if self._read_future is not None:
                assert callback is None
                future = self._read_future
                self._read_future = None
                future.set_result(self._consume(size))
        if callback is not None:
            assert (self._read_future is None) or streaming
            self._run_callback(callback, self._consume(size))
        else:
            # If we scheduled a callback, we will add the error listener
            # afterwards.  If we didn't, we have to do it now.
            self._maybe_add_error_listener()

    def _try_inline_read(self):
        """Attempt to complete the current read operation from buffered data.

        If the read can be completed without blocking, schedules the
        read callback on the next IOLoop iteration; otherwise starts
        listening for reads on the socket.
        """
        # See if we've already got the data from a previous read
        self._run_streaming_callback()
        pos = self._find_read_pos()
        if pos is not None:
            self._read_from_buffer(pos)
            return
        self._check_closed()
        try:
            pos = self._read_to_buffer_loop()
        except Exception:
            # If there was an in _read_to_buffer, we called close() already,
            # but couldn't run the close callback because of _pending_callbacks.
            # Before we escape from this function, run the close callback if
            # applicable.
            self._maybe_run_close_callback()
            raise
        if pos is not None:
            self._read_from_buffer(pos)
            return
        # We couldn't satisfy the read inline, so either close the stream
        # or listen for new data.
        if self.closed():
            self._maybe_run_close_callback()
        else:
            self._add_io_state(ioloop.IOLoop.READ)

    def _read_to_buffer(self):
        """Reads from the socket and appends the result to the read buffer.

        Returns the number of bytes read.  Returns 0 if there is nothing
        to read (i.e. the read returns EWOULDBLOCK or equivalent).  On
        error closes the socket and raises an exception.
        """
        try:
            chunk = self.read_from_fd()
        except (socket.error, IOError, OSError) as e:
            # ssl.SSLError is a subclass of socket.error
            if self._is_connreset(e):
                # Treat ECONNRESET as a connection close rather than
                # an error to minimize log spam  (the exception will
                # be available on self.error for apps that care).
                self.close(exc_info=True)
                return
            self.close(exc_info=True)
            raise
        if chunk is None:
            return 0
        self._read_buffer.append(chunk)
        self._read_buffer_size += len(chunk)
        if self._read_buffer_size > self.max_buffer_size:
            gen_log.error("Reached maximum read buffer size")
            self.close()
            raise StreamBufferFullError("Reached maximum read buffer size")
        return len(chunk)

    def _run_streaming_callback(self):
        if self._streaming_callback is not None and self._read_buffer_size:
            bytes_to_consume = self._read_buffer_size
            if self._read_bytes is not None:
                bytes_to_consume = min(self._read_bytes, bytes_to_consume)
                self._read_bytes -= bytes_to_consume
            self._run_read_callback(bytes_to_consume, True)

    def _read_from_buffer(self, pos):
        """Attempts to complete the currently-pending read from the buffer.

        The argument is either a position in the read buffer or None,
        as returned by _find_read_pos.
        """
        self._read_bytes = self._read_delimiter = self._read_regex = None
        self._read_partial = False
        self._run_read_callback(pos, False)

    def _find_read_pos(self):
        """Attempts to find a position in the read buffer that satisfies
        the currently-pending read.

        Returns a position in the buffer if the current read can be satisfied,
        or None if it cannot.
        """
        if (self._read_bytes is not None and
            (self._read_buffer_size >= self._read_bytes or
             (self._read_partial and self._read_buffer_size > 0))):
            num_bytes = min(self._read_bytes, self._read_buffer_size)
            return num_bytes
        elif self._read_delimiter is not None:
            # Multi-byte delimiters (e.g. '\r\n') may straddle two
            # chunks in the read buffer, so we can't easily find them
            # without collapsing the buffer.  However, since protocols
            # using delimited reads (as opposed to reads of a known
            # length) tend to be "line" oriented, the delimiter is likely
            # to be in the first few chunks.  Merge the buffer gradually
            # since large merges are relatively expensive and get undone in
            # _consume().
            if self._read_buffer:
                while True:
                    loc = self._read_buffer[0].find(self._read_delimiter)
                    if loc != -1:
                        delimiter_len = len(self._read_delimiter)
                        self._check_max_bytes(self._read_delimiter,
                                              loc + delimiter_len)
                        return loc + delimiter_len
                    if len(self._read_buffer) == 1:
                        break
                    _double_prefix(self._read_buffer)
                self._check_max_bytes(self._read_delimiter,
                                      len(self._read_buffer[0]))
        elif self._read_regex is not None:
            if self._read_buffer:
                while True:
                    m = self._read_regex.search(self._read_buffer[0])
                    if m is not None:
                        self._check_max_bytes(self._read_regex, m.end())
                        return m.end()
                    if len(self._read_buffer) == 1:
                        break
                    _double_prefix(self._read_buffer)
                self._check_max_bytes(self._read_regex,
                                      len(self._read_buffer[0]))
        return None

    def _check_max_bytes(self, delimiter, size):
        if (self._read_max_bytes is not None and
                size > self._read_max_bytes):
            raise UnsatisfiableReadError(
                "delimiter %r not found within %d bytes" % (
                    delimiter, self._read_max_bytes))

    def _handle_write(self):
        while self._write_buffer:
            try:
                if not self._write_buffer_frozen:
                    # On windows, socket.send blows up if given a
                    # write buffer that's too large, instead of just
                    # returning the number of bytes it was able to
                    # process.  Therefore we must not call socket.send
                    # with more than 128KB at a time.
                    _merge_prefix(self._write_buffer, 128 * 1024)
                num_bytes = self.write_to_fd(self._write_buffer[0])
                if num_bytes == 0:
                    # With OpenSSL, if we couldn't write the entire buffer,
                    # the very same string object must be used on the
                    # next call to send.  Therefore we suppress
                    # merging the write buffer after an incomplete send.
                    # A cleaner solution would be to set
                    # SSL_MODE_ACCEPT_MOVING_WRITE_BUFFER, but this is
                    # not yet accessible from python
                    # (http://bugs.python.org/issue8240)
                    self._write_buffer_frozen = True
                    break
                self._write_buffer_frozen = False
                _merge_prefix(self._write_buffer, num_bytes)
                self._write_buffer.popleft()
                self._write_buffer_size -= num_bytes
            except (socket.error, IOError, OSError) as e:
                if e.args[0] in _ERRNO_WOULDBLOCK:
                    self._write_buffer_frozen = True
                    break
                else:
                    if not self._is_connreset(e):
                        # Broken pipe errors are usually caused by connection
                        # reset, and its better to not log EPIPE errors to
                        # minimize log spam
                        gen_log.warning("Write error on %s: %s",
                                        self.fileno(), e)
                    self.close(exc_info=True)
                    return
        if not self._write_buffer:
            if self._write_callback:
                callback = self._write_callback
                self._write_callback = None
                self._run_callback(callback)
            if self._write_future:
                future = self._write_future
                self._write_future = None
                future.set_result(None)

    def _consume(self, loc):
        if loc == 0:
            return b""
        _merge_prefix(self._read_buffer, loc)
        self._read_buffer_size -= loc
        return self._read_buffer.popleft()

    def _check_closed(self):
        if self.closed():
            raise StreamClosedError("Stream is closed")

    def _maybe_add_error_listener(self):
        # This method is part of an optimization: to detect a connection that
        # is closed when we're not actively reading or writing, we must listen
        # for read events.  However, it is inefficient to do this when the
        # connection is first established because we are going to read or write
        # immediately anyway.  Instead, we insert checks at various times to
        # see if the connection is idle and add the read listener then.
        if self._pending_callbacks != 0:
            return
        if self._state is None or self._state == ioloop.IOLoop.ERROR:
            if self.closed():
                self._maybe_run_close_callback()
            elif (self._read_buffer_size == 0 and
                  self._close_callback is not None):
                self._add_io_state(ioloop.IOLoop.READ)

    def _add_io_state(self, state):
        """Adds `state` (IOLoop.{READ,WRITE} flags) to our event handler.

        Implementation notes: Reads and writes have a fast path and a
        slow path.  The fast path reads synchronously from socket
        buffers, while the slow path uses `_add_io_state` to schedule
        an IOLoop callback.  Note that in both cases, the callback is
        run asynchronously with `_run_callback`.

        To detect closed connections, we must have called
        `_add_io_state` at some point, but we want to delay this as
        much as possible so we don't have to set an `IOLoop.ERROR`
        listener that will be overwritten by the next slow-path
        operation.  As long as there are callbacks scheduled for
        fast-path ops, those callbacks may do more reads.
        If a sequence of fast-path ops do not end in a slow-path op,
        (e.g. for an @asynchronous long-poll request), we must add
        the error handler.  This is done in `_run_callback` and `write`
        (since the write callback is optional so we can have a
        fast-path write with no `_run_callback`)
        """
        if self.closed():
            # connection has been closed, so there can be no future events
            return
        if self._state is None:
            self._state = ioloop.IOLoop.ERROR | state
            with stack_context.NullContext():
                self.io_loop.add_handler(
                    self.fileno(), self._handle_events, self._state)
        elif not self._state & state:
            self._state = self._state | state
            self.io_loop.update_handler(self.fileno(), self._state)

    def _is_connreset(self, exc):
        """Return true if exc is ECONNRESET or equivalent.

        May be overridden in subclasses.
        """
        return (isinstance(exc, (socket.error, IOError)) and
                errno_from_exception(exc) in _ERRNO_CONNRESET)
