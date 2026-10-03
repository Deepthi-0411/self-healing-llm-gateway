import time

from app.gateway.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
)


def show_state(breaker):

    print(
        f"[Test] State: {breaker.state}"
    )

    print(
        f"[Test] Failure count: {breaker.failure_count}"
    )


def main():

    breaker = CircuitBreaker(
        provider_name="test-provider",
        failure_threshold=3,
        recovery_timeout=5,
    )

    print("\n========== INITIAL STATE ==========")

    show_state(breaker)

    print("\n========== FAILURE 1 ==========")

    breaker.record_failure()

    show_state(breaker)

    print("\n========== FAILURE 2 ==========")

    breaker.record_failure()

    show_state(breaker)

    print("\n========== FAILURE 3 ==========")

    breaker.record_failure()

    show_state(breaker)

    print(
        "\n[Test] Can execute:",
        breaker.can_execute()
    )

    print("\n========== WAITING FOR RECOVERY ==========")

    print("[Test] Waiting 5 seconds...")

    time.sleep(5)

    print("\n========== AFTER COOLDOWN ==========")

    print(
        "[Test] Can execute:",
        breaker.can_execute()
    )

    show_state(breaker)

    print("\n========== RECOVERY SUCCESS ==========")

    breaker.record_success()

    show_state(breaker)

    print(
        "\n[Test] Can execute:",
        breaker.can_execute()
    )


if __name__ == "__main__":
    main()