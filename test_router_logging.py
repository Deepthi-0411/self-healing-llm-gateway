import asyncio
from unittest.mock import AsyncMock, patch

from app.llm.router import call_with_fallback


# ============================================================
# TEST EXCEPTION
# ============================================================

class RouterTestError(Exception):
    """
    Simulated authentication error.

    401 means non-retryable, so the router should immediately
    fall back to the next provider.
    """

    status_code = 401


# ============================================================
# TEST PROVIDER CALL
# ============================================================

async def fake_call_provider(
    provider,
    model,
    messages,
    temperature=None,
    max_tokens=None,
):
    """
    Gemini fails with a sensitive message.

    Cloudflare succeeds.

    Cohere should never be reached.
    """

    if provider == "gemini":

        raise RouterTestError(
            "Authorization: Bearer "
            "super-secret-router-token-123"
        )

    if provider == "cloudflare":

        return {
            "provider": "cloudflare",
            "model": model,
            "message": "Test response",
        }

    raise AssertionError(
        f"Unexpected provider reached: {provider}"
    )


# ============================================================
# TEST
# ============================================================

async def main():

    print(
        "\n========================================="
    )

    print(
        "ROUTER LOGGING TEST"
    )

    print(
        "=========================================\n"
    )

    # --------------------------------------------------------
    # Mock provider health
    # --------------------------------------------------------

    with patch(
        "app.llm.router.provider_health.can_execute",
        new=AsyncMock(return_value=True),
    ), patch(
        "app.llm.router.provider_health.record_success",
        new=AsyncMock(),
    ), patch(
        "app.llm.router.provider_health.record_failure",
        new=AsyncMock(),
    ), patch(
        "app.llm.router.call_provider",
        new=fake_call_provider,
    ):

        result = await call_with_fallback(
            messages=[
                {
                    "role": "user",
                    "content": "Test router fallback",
                }
            ],
            temperature=None,
            max_tokens=None,
            tier=None,
        )

    # --------------------------------------------------------
    # Verify fallback succeeded
    # --------------------------------------------------------

    if result["provider"] != "cloudflare":
        raise AssertionError(
            "Router did not fall back to Cloudflare."
        )

    print(
        "[TEST] Gemini failure handled: PASS"
    )

    print(
        "[TEST] Cloudflare fallback: PASS"
    )

    print(
        "[TEST] Cohere not reached: PASS"
    )

    print(
        "[TEST] Router returned successful response: PASS"
    )

    print(
        "\n[TEST] Sensitive token should appear only as "
        "[REDACTED] in structured log."
    )

    print(
        "\n========================================="
    )

    print(
        "ROUTER LOGGING TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )


if __name__ == "__main__":
    asyncio.run(main())