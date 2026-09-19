class InvalidImage(ValueError):
    """The input is unsupported, damaged, animated, or exceeds image limits."""


class InvalidStorageKey(ValueError):
    """The storage key is invalid or points outside the media directory."""


class MediaStorageError(Exception):
    """The media storage could not complete an operation."""
