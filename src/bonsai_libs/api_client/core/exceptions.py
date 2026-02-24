"""API client error handling."""

class ApiError(Exception):
    """Base class for all API-related errors."""
    status: int | None = None

    def __init__(self, message: str, *, status: int | None = None, body: str | None = None):
        super().__init__(message)
        self.status = status
        self.body = body


class ClientError(ApiError):
    """Base for 4xx errors."""


class ServerError(ApiError):
    """Base for 5xx errors."""


# ---- 4xx ----

class BadRequestError(ClientError):             status = 400
class UnauthorizedError(ClientError):           status = 401
class ForbiddenError(ClientError):              status = 403
class NotFoundError(ClientError):               status = 404
class ConflictError(ClientError):               status = 409
class UnprocessableEntityError(ClientError):    status = 422
class TooManyRequestsError(ClientError):        status = 429

# ---- non-HTTP-level errors ----

class NetworkError(ApiError):
    """Network-level errors before receiving a response."""

class TimeoutError(NetworkError):
    """Connection or read timeout."""

class ConnectionFailedError(NetworkError):
    """Network connectivity issues."""

class ApiRequestFailed(ApiError):
    """Request exhausted retries and ultimately failed."""

_STATUS_TO_ERROR: dict[int, type[ApiError]] = {
    400: BadRequestError,
    401: UnauthorizedError,
    403: ForbiddenError,
    404: NotFoundError,
    409: ConflictError,
    422: UnprocessableEntityError,
    429: TooManyRequestsError,
}


def raise_for_status(status: int, body: str | None = None) -> None:
    """Raise a precise error based on the HTTP status code."""
    message = body or f"HTTP {status}"

    if 400 <= status < 500:
        exc_cls = _STATUS_TO_ERROR.get(status, ClientError)
        raise exc_cls(message, status=status, body=body)

    if 500 <= status:
        raise ServerError(message, status=status, body=body)