# smell: LongMessageChain
# validated by: PySmell manual inspection (Chen et al.)
# origin: https://github.com/django/django/blob/1.8.2/tests/middleware_exceptions/tests.py#L133-L138
# smelly line(s) in the original file: 135
# smelly line(s) in this file: 10
# ids: pysmell_1381
# note: Python 2 era source, kept as found
def _add_middleware(self, middleware):
    self.client.handler._request_middleware.insert(0, middleware.process_request)
    self.client.handler._view_middleware.insert(0, middleware.process_view)
    self.client.handler._template_response_middleware.append(middleware.process_template_response)
    self.client.handler._response_middleware.append(middleware.process_response)
    self.client.handler._exception_middleware.append(middleware.process_exception)
