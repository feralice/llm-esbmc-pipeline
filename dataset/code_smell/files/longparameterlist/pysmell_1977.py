# smell: LongParameterList
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/django/http/multipartparser.py#L52-L105
# smelly line(s) in the original file: 52
# smelly line(s) in this file: 8
# ids: pysmell_1977
# note: Python 2 era source, kept as found
def __init__(self, META, input_data, upload_handlers, encoding=None):
    """
    Initialize the MultiPartParser object.

    :META:
        The standard ``META`` dictionary in Django request objects.
    :input_data:
        The raw post data, as a file-like object.
    :upload_handlers:
        A list of UploadHandler instances that perform operations on the uploaded
        data.
    :encoding:
        The encoding with which to treat the incoming data.
    """

    #
    # Content-Type should contain multipart and the boundary information.
    #

    content_type = META.get('HTTP_CONTENT_TYPE', META.get('CONTENT_TYPE', ''))
    if not content_type.startswith('multipart/'):
        raise MultiPartParserError('Invalid Content-Type: %s' % content_type)

    # Parse the header to get the boundary to split the parts.
    ctypes, opts = parse_header(content_type.encode('ascii'))
    boundary = opts.get('boundary')
    if not boundary or not cgi.valid_boundary(boundary):
        raise MultiPartParserError('Invalid boundary in multipart: %s' % boundary)

    # Content-Length should contain the length of the body we are about
    # to receive.
    try:
        content_length = int(META.get('HTTP_CONTENT_LENGTH', META.get('CONTENT_LENGTH', 0)))
    except (ValueError, TypeError):
        content_length = 0

    if content_length < 0:
        # This means we shouldn't continue...raise an error.
        raise MultiPartParserError("Invalid content length: %r" % content_length)

    if isinstance(boundary, six.text_type):
        boundary = boundary.encode('ascii')
    self._boundary = boundary
    self._input_data = input_data

    # For compatibility with low-level network APIs (with 32-bit integers),
    # the chunk size should be < 2^31, but still divisible by 4.
    possible_sizes = [x.chunk_size for x in upload_handlers if x.chunk_size]
    self._chunk_size = min([2 ** 31 - 4] + possible_sizes)

    self._meta = META
    self._encoding = encoding or settings.DEFAULT_CHARSET
    self._content_length = content_length
    self._upload_handlers = upload_handlers
