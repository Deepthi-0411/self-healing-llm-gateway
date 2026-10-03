import asyncio

from app.gateway.errors import (
    ErrorCategory,
    classify_error,
)
from app.gateway.request_logger import (
    log_event,
)


# ============================================================
# RETRY CONFIGURATION
# ============================================================

MAX_RETRIES = 2


# ============================================================
# RETRY DELAY
# ============================================================

async def wait_before_retry(
    attempt: int,
):
    """
    Exponential backoff.

    Attempt 1 -> 1 second
    Attempt 2 -> 2 seconds
    """

    delay = 2 ** (attempt - 1)

    log_event(
        "retry_wait",
        request_attempt=attempt,
        delay_seconds=delay,
    )

    await asyncio.sleep(
        delay
    )


# ============================================================
# SHOULD RETRY
# ============================================================

def should_retry(
    category: ErrorCategory,
) -> bool:
    """
    Determine whether an error should be retried.
    """

    return category in {
        ErrorCategory.RETRYABLE,
        ErrorCategory.RATE_LIMIT,
    }


# ============================================================
# CALL WITH RETRY
# ============================================================

async def call_with_retry(
    call_function,
    messages,
    temperature=None,
    max_tokens=None,
):
    """
    Execute an LLM call with retry and exponential backoff.

    The actual retry behavior is unchanged.

    Error messages are passed through the structured logger,
    which applies PII/secret redaction before logging.
    """

    for attempt in range(
        MAX_RETRIES + 1
    ):

        try:

            return await call_function(
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        except Exception as error:

            category = classify_error(
                error
            )

            # ------------------------------------------------
            # Log retry failure safely
            # ------------------------------------------------

            log_event(
                "retry_attempt_failed",
                level="WARNING",
                attempt=attempt + 1,
                max_attempts=MAX_RETRIES + 1,
                error_type=type(error).__name__,
                error_message=str(error),
                error_category=category.value,
            )

            # ------------------------------------------------
            # Maximum retry count reached
            # ------------------------------------------------

            if attempt >= MAX_RETRIES:

                log_event(
                    "retry_exhausted",
                    level="ERROR",
                    attempts=MAX_RETRIES + 1,
                    error_type=type(error).__name__,
                    error_category=category.value,
                )

                raise

            # ------------------------------------------------
            # Error is not retryable
            # ------------------------------------------------

            if not should_retry(
                category
            ):

                log_event(
                    "retry_not_allowed",
                    level="WARNING",
                    attempt=attempt + 1,
                    error_type=type(error).__name__,
                    error_category=category.value,
                )

                raise

            # ------------------------------------------------
            # Retry
            # ------------------------------------------------

            await wait_before_retry(
                attempt + 1
            )

    raise RuntimeError(
        "Retry loop exited unexpectedly."
    )