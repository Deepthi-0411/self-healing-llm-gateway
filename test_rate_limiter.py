import asyncio

from app.gateway.rate_limiter import (
    RedisRateLimiter,
)


async def main():

    print(
        "\n========================================="
    )

    print(
        "REDIS RATE LIMITER TEST"
    )

    print(
        "=========================================\n"
    )

    limiter = RedisRateLimiter(
        default_limit=3,
        window_seconds=10,
    )

    # Use a dedicated test tenant so we don't
    # interfere with your normal gateway tenant.
    tenant = "rate-limit-test-tenant"

    for request_number in range(1, 6):

        result = await limiter.check(
            tenant
        )

        print(
            f"[TEST] Request #{request_number}"
        )

        print(
            f"[TEST] Allowed: "
            f"{result.allowed}"
        )

        print(
            f"[TEST] Current: "
            f"{result.current}"
        )

        print(
            f"[TEST] Limit: "
            f"{result.limit}"
        )

        print(
            f"[TEST] Remaining: "
            f"{result.remaining}"
        )

        print(
            f"[TEST] Retry after: "
            f"{result.retry_after}s"
        )

        print()


    print(
        "=========================================\n"
    )


if __name__ == "__main__":
    asyncio.run(main())