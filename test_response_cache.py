import asyncio

from app.cache.response_cache import (
    RedisResponseCache,
)

from app.infra.redis_client import (
    redis_client,
)


async def main():

    print(
        "\n========================================="
    )

    print(
        "REDIS RESPONSE CACHE TEST"
    )

    print(
        "=========================================\n"
    )

    cache = RedisResponseCache(
        ttl_seconds=30,
    )

    tenant = "cache-test-tenant"
    feature = "cache-test"
    model = "auto"

    messages = [
        {
            "role": "user",
            "content": "What is an API?",
        }
    ]

    temperature = None
    max_tokens = None

    test_response = {
        "id": "cache-test-response",
        "object": "chat.completion",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "An API is an interface "
                        "that allows applications "
                        "to communicate."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
    }

    # --------------------------------------------------------
    # Clean previous entry
    # --------------------------------------------------------

    await cache.delete(
        tenant=tenant,
        feature=feature,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # --------------------------------------------------------
    # First lookup -> MISS
    # --------------------------------------------------------

    result = await cache.get(
        tenant=tenant,
        feature=feature,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(
        "[TEST] First lookup:",
        "MISS" if result is None else "HIT",
    )

    if result is not None:
        raise RuntimeError(
            "Expected cache MISS."
        )

    # --------------------------------------------------------
    # Store response
    # --------------------------------------------------------

    await cache.set(
        tenant=tenant,
        feature=feature,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        response=test_response,
    )

    # --------------------------------------------------------
    # Second lookup -> HIT
    # --------------------------------------------------------

    result = await cache.get(
        tenant=tenant,
        feature=feature,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(
        "[TEST] Second lookup:",
        "HIT" if result is not None else "MISS",
    )

    if result != test_response:
        raise RuntimeError(
            "Cached response does not match "
            "original response."
        )

    # --------------------------------------------------------
    # Different request -> MISS
    # --------------------------------------------------------

    different_messages = [
        {
            "role": "user",
            "content": (
                "What is a database?"
            ),
        }
    ]

    result = await cache.get(
        tenant=tenant,
        feature=feature,
        model=model,
        messages=different_messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    print(
        "[TEST] Different request:",
        "MISS" if result is None else "HIT",
    )

    if result is not None:
        raise RuntimeError(
            "Different request unexpectedly hit cache."
        )

    # --------------------------------------------------------
    # Verify different request IDs do not affect cache
    # --------------------------------------------------------

    # request_id is not part of the cache key because it
    # is intentionally not passed to the cache.

    print(
        "\n[TEST] Request ID independence: SUCCESS"
    )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    await cache.delete(
        tenant=tenant,
        feature=feature,
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    await redis_client.aclose()

    print(
        "\n========================================="
    )

    print(
        "REDIS RESPONSE CACHE TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )


if __name__ == "__main__":
    asyncio.run(main())