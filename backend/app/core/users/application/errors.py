class UserAlreadyExistsError(ValueError):
    pass


class UserNotFoundError(ValueError):
    pass


class RoleNotFoundError(ValueError):
    pass


class UserConflictError(ValueError):
    pass


class InvalidPasswordLinkError(ValueError):
    pass


class MailDeliveryError(RuntimeError):
    pass
