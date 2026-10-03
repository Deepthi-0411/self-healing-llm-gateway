import threading
import time


class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:

    def __init__(
        self,
        provider_name: str,
        failure_threshold: int = 3,
        recovery_timeout: int = 10,
    ):
        self.provider_name = provider_name

        self.failure_threshold = (
            failure_threshold
        )

        self.recovery_timeout = (
            recovery_timeout
        )

        self.failure_count = 0

        self.state = (
            CircuitState.CLOSED
        )

        self.opened_at = None

        self.lock = threading.Lock()

        self.half_open_probe_in_progress = False

    # ========================================================
    # SUCCESS
    # ========================================================

    def record_success(self):
        with self.lock:

            previous_state = self.state
            self.failure_count = 0 
            self.state = CircuitState.CLOSED
            self.opened_at = None
            self.half_open_probe_in_progress = False
            if previous_state != CircuitState.CLOSED:
                print(
                    f"[CircuitBreaker] "
                    f"Provider: {self.provider_name} | "
                    f"State changed: "
                    f"{previous_state.upper()} -> CLOSED"
                )

            print(
                f"[CircuitBreaker] "
                f"Provider: {self.provider_name} | "
                f"Success recorded. "
                f"Failure count: 0"
            )

            

    # ========================================================
    # FAILURE
    # ========================================================

    def record_failure(self):
        with self.lock:

            # Recovery probe failed.
            if (
                self.state
                == CircuitState.HALF_OPEN
            ):
                self.state = (
                    CircuitState.OPEN
                )

                self.opened_at = (
                    time.time()
                )

                self.failure_count = (
                    self.failure_threshold
                )

                self.half_open_probe_in_progress = (
                    False
                )

                print(
                    f"[CircuitBreaker] "
                    f"Provider: {self.provider_name} | "
                    f"State changed: "
                    f"HALF_OPEN -> OPEN"
                )

                return

            self.failure_count += 1

            print(
                f"[CircuitBreaker] "
                f"Provider: {self.provider_name} | "
                f"Failure count: "
                f"{self.failure_count}"
            )

            if (
                self.failure_count
                >= self.failure_threshold
            ):

                self.state = (
                    CircuitState.OPEN
                )

                self.opened_at = (
                    time.time()
                )

                self.half_open_probe_in_progress = (
                    False
                )

                print(
                    f"[CircuitBreaker] "
                    f"Provider: {self.provider_name} | "
                    f"State changed: "
                    f"CLOSED -> OPEN"
                )

    # ========================================================
    # CAN EXECUTE
    # ========================================================

    def can_execute(self) -> bool:

        with self.lock:

            print(
                f"[CircuitBreaker] "
                f"Provider: {self.provider_name} | "
                f"Checking state: "
                f"{self.state}, "
                f"failures: "
                f"{self.failure_count}"
            )

            # ---------------------------------------------
            # CLOSED
            # ---------------------------------------------

            if (
                self.state
                == CircuitState.CLOSED
            ):
                return True

            # ---------------------------------------------
            # OPEN
            # ---------------------------------------------

            if (
                self.state
                == CircuitState.OPEN
            ):

                if self.opened_at is None:
                    return False

                elapsed = (
                    time.time()
                    - self.opened_at
                )

                print(
                    f"[CircuitBreaker] "
                    f"Provider: {self.provider_name} | "
                    f"Open for "
                    f"{elapsed:.2f} seconds"
                )

                if (
                    elapsed
                    >= self.recovery_timeout
                ):

                    self.state = (
                        CircuitState.HALF_OPEN
                    )

                    self.half_open_probe_in_progress = (
                        True
                    )

                    print(
                        f"[CircuitBreaker] "
                        f"Provider: {self.provider_name} | "
                        f"State changed: "
                        f"OPEN -> HALF_OPEN"
                    )

                    print(
                        f"[CircuitBreaker] "
                        f"Provider: {self.provider_name} | "
                        f"Recovery probe reserved."
                    )

                    return True

                return False

            # ---------------------------------------------
            # HALF OPEN
            # ---------------------------------------------

            if (
                self.state
                == CircuitState.HALF_OPEN
            ):

                if (
                    self.half_open_probe_in_progress
                ):

                    print(
                        f"[CircuitBreaker] "
                        f"Provider: {self.provider_name} | "
                        f"Recovery probe already "
                        f"in progress. "
                        f"Rejecting request."
                    )

                    return False

                self.half_open_probe_in_progress = (
                    True
                )

                print(
                    f"[CircuitBreaker] "
                    f"Provider: {self.provider_name} | "
                    f"Recovery probe reserved."
                )

                return True

            return False