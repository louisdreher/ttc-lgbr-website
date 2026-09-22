class InvalidImage(ValueError):
    """The input is unsupported, damaged, animated, or exceeds image limits."""


class InvalidStorageKey(ValueError):
    """The storage key is invalid or points outside the media directory."""


class MediaStorageError(Exception):
    """The media storage could not complete an operation."""


class ImageNotFound(Exception):
    """The image is missing or unavailable to this user."""


class GalleryAccessDenied(Exception):
    pass


class EventGalleryAlreadyExists(Exception):
    pass


class GalleryNotFound(Exception):
    pass


class GalleryConflict(Exception):
    pass
