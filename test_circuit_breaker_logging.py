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
        "CIRCUIT BREAKER LOGGING TEST"
    )

    print(
        "=========================================\n"
    )

    provider = "gemini"

    breaker = RedisCircuitBreaker(
        provider_name=provider,
        failure_threshold=3,
        recovery_timeout=2,
    )

    # --------------------------------------------------------
    # Reset state
    # --------------------------------------------------------

    await breaker.reset()

    # --------------------------------------------------------
    # Initial state
    # --------------------------------------------------------

    state = await breaker.get_state()

    if state != CircuitState.CLOSED:
        raise AssertionError(
            f"Expected CLOSED, got {state}"
        )

    print(
        "[TEST] Initial CLOSED state: PASS"
    )

    # --------------------------------------------------------
    # CLOSED should allow execution
    # --------------------------------------------------------

    allowed = await breaker.can_execute()

    if not allowed:
        raise AssertionError(
            "CLOSED circuit should allow execution."
        )

    print(
        "[TEST] CLOSED allows execution: PASS"
    )

    # --------------------------------------------------------
    # Record 3 failures
    # --------------------------------------------------------

    await breaker.record_failure()
    await breaker.record_failure()
    await breaker.record_failure()

    state = await breaker.get_state()

    if state != CircuitState.OPEN:
        raise AssertionError(
            f"Expected OPEN, got {state}"
        )

    print(
        "[TEST] Failure threshold opens circuit: PASS"
    )

    # --------------------------------------------------------
    # OPEN should block execution
    # --------------------------------------------------------

    allowed = await breaker.can_execute()

    if allowed:
        raise AssertionError(
            "OPEN circuit should block execution."
        )

    print(
        "[TEST] OPEN blocks execution: PASS"
    )

    # --------------------------------------------------------
    # Wait for recovery
    # --------------------------------------------------------

    print(
        "[TEST] Waiting for recovery timeout..."
    )

    await asyncio.sleep(2.2)

    # --------------------------------------------------------
    # OPEN -> HALF_OPEN
    # --------------------------------------------------------

    allowed = await breaker.can_execute()

    if not allowed:
        raise AssertionError(
            "Recovery probe should be allowed."
        )

    state = await breaker.get_state()

    if state != CircuitState.HALF_OPEN:
        raise AssertionError(
            f"Expected HALF_OPEN, got {state}"
        )

    print(
        "[TEST] OPEN -> HALF_OPEN: PASS"
    )

    # --------------------------------------------------------
    # Recovery probe succeeds
    # --------------------------------------------------------

    await breaker.record_success()

    state = await breaker.get_state()

    if state != CircuitState.CLOSED:
        raise AssertionError(
            f"Expected CLOSED after success, got {state}"
        )

    print(
        "[TEST] HALF_OPEN -> CLOSED: PASS"
    )

    # --------------------------------------------------------
    # Cleanup
    # --------------------------------------------------------

    await breaker.reset()

    print(
        "\n========================================="
    )

    print(
        "CIRCUIT BREAKER LOGGING TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )


if __name__ == "__main__":

    asyncio.run(main())