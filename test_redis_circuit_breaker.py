import asyncio

from app.gateway.redis_circuit_breaker import (
    CircuitState,
    RedisCircuitBreaker,
)


async def main():

    print(
        "\n========================================="
    )

    print(
        "REDIS CIRCUIT BREAKER TEST"
    )

    print(
        "=========================================\n"
    )

    breaker = RedisCircuitBreaker(
        provider_name="test-provider",
        failure_threshold=3,
        recovery_timeout=3,
    )

    # --------------------------------------------------------
    # Clean previous test state
    # --------------------------------------------------------

    await breaker.reset()

    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------

    print(
        "\n[TEST] Checking initial state..."
    )

    allowed = await breaker.can_execute()

    print(
        "[TEST] Can execute:",
        allowed,
    )

    # --------------------------------------------------------
    # Failure 1
    # --------------------------------------------------------

    print(
        "\n[TEST] Recording failure #1..."
    )

    await breaker.record_failure()

    # --------------------------------------------------------
    # Failure 2
    # --------------------------------------------------------

    print(
        "\n[TEST] Recording failure #2..."
    )

    await breaker.record_failure()

    # --------------------------------------------------------
    # Failure 3 -> OPEN
    # --------------------------------------------------------

    print(
        "\n[TEST] Recording failure #3..."
    )

    await breaker.record_failure()

    state = await breaker.get_state()

    print(
        "[TEST] Current state:",
        state,
    )

    if state != CircuitState.OPEN:
        raise RuntimeError(
            "Circuit did not enter OPEN state."
        )

    # --------------------------------------------------------
    # Immediate request should be blocked
    # --------------------------------------------------------

    print(
        "\n[TEST] Checking while OPEN..."
    )

    allowed = await breaker.can_execute()

    print(
        "[TEST] Can execute:",
        allowed,
    )

    if allowed:
        raise RuntimeError(
            "Circuit allowed execution while OPEN."
        )

    # --------------------------------------------------------
    # Wait for recovery timeout
    # --------------------------------------------------------

    print(
        "\n[TEST] Waiting for recovery timeout..."
    )

    await asyncio.sleep(3.2)

    # --------------------------------------------------------
    # Recovery probe
    # --------------------------------------------------------

    print(
        "\n[TEST] Requesting recovery probe..."
    )

    allowed = await breaker.can_execute()

    print(
        "[TEST] Recovery probe allowed:",
        allowed,
    )

    if not allowed:
        raise RuntimeError(
            "Recovery probe was not allowed."
        )

    state = await breaker.get_state()

    print(
        "[TEST] State after probe:",
        state,
    )

    if state != CircuitState.HALF_OPEN:
        raise RuntimeError(
            "Circuit did not enter HALF_OPEN state."
        )

    # --------------------------------------------------------
    # Second concurrent probe should be blocked
    # --------------------------------------------------------

    print(
        "\n[TEST] Checking second probe..."
    )

    second_probe = await breaker.can_execute()

    print(
        "[TEST] Second probe allowed:",
        second_probe,
    )

    if second_probe:
        raise RuntimeError(
            "More than one recovery probe was allowed."
        )

    # --------------------------------------------------------
    # Recovery success
    # --------------------------------------------------------

    print(
        "\n[TEST] Recording recovery success..."
    )

    await breaker.record_success()

    state = await breaker.get_state()

    failures = await breaker.get_failure_count()

    print(
        "[TEST] Final state:",
        state,
    )

    print(
        "[TEST] Final failure count:",
        failures,
    )

    if state != CircuitState.CLOSED:
        raise RuntimeError(
            "Circuit did not return to CLOSED."
        )

    if failures != 0:
        raise RuntimeError(
            "Failure count was not reset."
        )

    print(
        "\n========================================="
    )

    print(
        "REDIS CIRCUIT BREAKER TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )

    await breaker.reset()


if __name__ == "__main__":
    asyncio.run(main())