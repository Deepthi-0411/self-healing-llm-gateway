from enum import Enum


class ErrorCategory(str, Enum):
    RETRYABLE = "retryable"
    RATE_LIMIT = "rate_limit"
    NON_RETRYABLE = "non_retryable"
    UNKNOWN = "unknown"


def classify_error(error: Exception) -> ErrorCategory:
    """
    Convert provider-specific exceptions into common
    gateway-level error categories.
    """

    error_name = type(error).__name__

    # ---------------------------------------------------------
    # HTTP status based classification
    # ---------------------------------------------------------

    status_code = getattr(
        error,
        "status_code",
        None,
    )

    if status_code == 429:
        return ErrorCategory.RATE_LIMIT

    if status_code in {
        408,
        425,
        500,
        502,
        503,
        504,
    }:
        return ErrorCategory.RETRYABLE

    if status_code in {
        400,
        401,
        403,
        404,
        405,
        409,
        422,
    }:
        return ErrorCategory.NON_RETRYABLE

    # ---------------------------------------------------------
    # Exception name based classification
    # ---------------------------------------------------------

    if error_name == "RateLimitError":
        return ErrorCategory.RATE_LIMIT

    if error_name in {
        "Timeout",
        "TimeoutError",
        "APITimeoutError",
        "ReadTimeout",
        "ConnectTimeout",
    }:
        return ErrorCategory.RETRYABLE

    if error_name in {
        "InternalServerError",
        "APIConnectionError",
        "ServiceUnavailableError",
        "APIConnectError",
    }:
        return ErrorCategory.RETRYABLE

    if error_name in {
        "AuthenticationError",
        "PermissionDeniedError",
        "UnauthorizedError",
    }:
        return ErrorCategory.NON_RETRYABLE

    if error_name in {
        "BadRequestError",
        "InvalidRequestError",
    }:
        return ErrorCategory.NON_RETRYABLE

    return ErrorCategory.UNKNOWN