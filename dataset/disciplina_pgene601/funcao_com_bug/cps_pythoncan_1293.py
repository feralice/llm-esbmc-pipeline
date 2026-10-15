class IscanError:
    def __init__(self, function, error_code: int, arguments) -> None:
        try:
            description = ": " + self.ERROR_CODES[self.error_code]
        except KeyError:
            description = ""

        super().__init__(
            f"Function {self.function.__name__} failed{description}",
            error_code=error_code,
        )

        #: Status code
        self.error_code = error_code
        #: Function that failed
        self.function = function
        #: Arguments passed to function
        self.arguments = arguments
