class SourceError(RuntimeError):
    """Provider failure with transport-independent retry information."""

    def __init__(self, message: str, *, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable
