class DomainError(Exception):
    status_code = 400

    def __init__(self, message: str, **details):
        super().__init__(message)
        self.message = message
        self.details = details


class NotFound(DomainError):
    status_code = 404


class Conflict(DomainError):
    status_code = 409


class Forbidden(DomainError):
    status_code = 403


class InvalidTransition(DomainError):
    status_code = 409


class InsufficientStock(DomainError):
    status_code = 409
