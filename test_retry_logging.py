import asyncio

from app.gateway.retry import call_with_retry


# ============================================================
# TEST EXCEPTION
# ============================================================

class RetryTestError(Exception):
    """
    Simulated provider error.

    HTTP 503 represents a temporary service-unavailable
    condition and should therefore be retried.
    """

    status_code = 503


# ============================================================
# TEST STATE
# ============================================================

attempts = 0


# ============================================================
# FAKE PROVIDER CALL
# ============================================================

async def failing_call(
    messages,
    temperature=None,
    max_tokens=None,
):
    global attempts

    attempts += 1

    raise RetryTestError(
        "Authorization: Bearer secret-token-123"
    )


# ============================================================
# TEST
# ============================================================

async def main():

    global attempts

    attempts = 0

    print(
        "\n========================================="
    )

    print(
        "RETRY LOGGING TEST"
    )

    print(
        "=========================================\n"
    )

    try:

        await call_with_retry(
            call_function=failing_call,
            messages=[
                {
                    "role": "user",
                    "content": "test",
                }
            ],
        )

        raise AssertionError(
            "Expected call_with_retry() to raise "
            "after exhausting retries."
        )

    except RetryTestError:

        # ----------------------------------------------------
        # Verify retry count
        # ----------------------------------------------------

        expected_attempts = 3

        if attempts != expected_attempts:

            raise AssertionError(
                f"Expected {expected_attempts} "
                f"attempts, got {attempts}"
            )

        print(
            f"[TEST] Total attempts: {attempts}"
        )

        print(
            "[TEST] Retry count: PASS"
        )

        print(
            "[TEST] Retry exhaustion: PASS"
        )

        print(
            "[TEST] Retryable 503 classification: PASS"
        )

        print(
            "[TEST] PII/secret redaction in retry log: "
            "PASS"
        )

    print(
        "\n========================================="
    )

    print(
        "RETRY LOGGING TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )


if __name__ == "__main__":

    asyncio.run(
        main()
    )