class ContractsManager:
    def _clean_req(self, request, method, results):
        ...
        def eb_wrapper(failure):
            case = _create_testcase(method, 'errback')
            exc_info = failure.value, failure.type, failure.getTracebackObject()
            results.addError(case, exc_info)
