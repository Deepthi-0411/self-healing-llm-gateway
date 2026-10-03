import time

from app.gateway.request_logger import (
    log_event,
)
from app.infra.redis_client import (
    redis_client,
)


# ============================================================
# CIRCUIT STATES
# ============================================================

class CircuitState:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# ============================================================
# REDIS CIRCUIT BREAKER
# ============================================================

class RedisCircuitBreaker:

    def __init__(
        self,
        provider_name,
        failure_threshold=3,
        recovery_timeout=10,
    ):
        self.provider_name = provider_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self.key_prefix = (
            f"gateway:circuit:{provider_name}"
        )

        self.state_key = (
            f"{self.key_prefix}:state"
        )

        self.failure_key = (
            f"{self.key_prefix}:failures"
        )

        self.opened_at_key = (
            f"{self.key_prefix}:opened_at"
        )

        self.probe_key = (
            f"{self.key_prefix}:probe"
        )

    # ========================================================
    # RESET
    # ========================================================

    async def reset(self):

        await redis_client.delete(
            self.state_key,
            self.failure_key,
            self.opened_at_key,
            self.probe_key,
        )

        log_event(
            "circuit_breaker_reset",
            provider=self.provider_name,
        )

    # ========================================================
    # GET STATE
    # ========================================================

    async def get_state(self):

        state = await redis_client.get(
            self.state_key
        )

        return (
            state
            if state is not None
            else CircuitState.CLOSED
        )

    # ========================================================
    # GET FAILURE COUNT
    # ========================================================

    async def get_failure_count(self):

        value = await redis_client.get(
            self.failure_key
        )

        return (
            0
            if value is None
            else int(value)
        )

    # ========================================================
    # CAN EXECUTE
    # ========================================================

    async def can_execute(self):

        state = await self.get_state()
        failure_count = (
            await self.get_failure_count()
        )

        log_event(
            "circuit_breaker_check",
            provider=self.provider_name,
            state=state,
            failure_count=failure_count,
        )

        # ----------------------------------------------------
        # CLOSED
        # ----------------------------------------------------

        if state == CircuitState.CLOSED:

            return True

        # ----------------------------------------------------
        # HALF OPEN
        # ----------------------------------------------------

        if state == CircuitState.HALF_OPEN:

            probe_reserved = await redis_client.set(
                self.probe_key,
                "1",
                nx=True,
                ex=self.recovery_timeout,
            )

            if not probe_reserved:

                log_event(
                    "circuit_probe_already_reserved",
                    level="INFO",
                    provider=self.provider_name,
                    state=state,
                )

                return False

            log_event(
                "circuit_recovery_probe_reserved",
                provider=self.provider_name,
                state=state,
            )

            return True

        # ----------------------------------------------------
        # OPEN
        # ----------------------------------------------------

        if state == CircuitState.OPEN:

            opened_at = await redis_client.get(
                self.opened_at_key
            )

            if opened_at is None:

                log_event(
                    "circuit_open_missing_timestamp",
                    level="WARNING",
                    provider=self.provider_name,
                )

                return False

            elapsed = (
                time.time()
                - float(opened_at)
            )

            log_event(
                "circuit_open_check",
                provider=self.provider_name,
                state=state,
                elapsed_seconds=round(
                    elapsed,
                    3,
                ),
                recovery_timeout=(
                    self.recovery_timeout
                ),
            )

            # ------------------------------------------------
            # Still inside recovery timeout
            # ------------------------------------------------

            if (
                elapsed
                < self.recovery_timeout
            ):

                log_event(
                    "circuit_request_blocked",
                    level="WARNING",
                    provider=self.provider_name,
                    state=state,
                    elapsed_seconds=round(
                        elapsed,
                        3,
                    ),
                    recovery_timeout=(
                        self.recovery_timeout
                    ),
                )

                return False

            # ------------------------------------------------
            # Recovery period completed
            # ------------------------------------------------

            probe_reserved = await redis_client.set(
                self.probe_key,
                "1",
                nx=True,
                ex=self.recovery_timeout,
            )

            if not probe_reserved:

                log_event(
                    "circuit_probe_already_reserved",
                    level="INFO",
                    provider=self.provider_name,
                    state=state,
                )

                return False

            await redis_client.set(
                self.state_key,
                CircuitState.HALF_OPEN,
            )

            log_event(
                "circuit_state_changed",
                provider=self.provider_name,
                previous_state=CircuitState.OPEN,
                new_state=CircuitState.HALF_OPEN,
            )

            log_event(
                "circuit_recovery_probe_reserved",
                provider=self.provider_name,
                state=CircuitState.HALF_OPEN,
            )

            return True

        return False

    # ========================================================
    # RECORD SUCCESS
    # ========================================================

    async def record_success(self):

        previous_state = (
            await self.get_state()
        )

        await redis_client.set(
            self.failure_key,
            0,
        )

        await redis_client.set(
            self.state_key,
            CircuitState.CLOSED,
        )

        await redis_client.delete(
            self.opened_at_key,
            self.probe_key,
        )

        if (
            previous_state
            != CircuitState.CLOSED
        ):

            log_event(
                "circuit_state_changed",
                provider=self.provider_name,
                previous_state=previous_state,
                new_state=CircuitState.CLOSED,
            )

        log_event(
            "circuit_success_recorded",
            provider=self.provider_name,
            state=CircuitState.CLOSED,
            failure_count=0,
        )

    # ========================================================
    # RECORD FAILURE
    # ========================================================

    async def record_failure(self):

        state = await self.get_state()

        # ----------------------------------------------------
        # HALF OPEN FAILURE
        # ----------------------------------------------------

        if state == CircuitState.HALF_OPEN:

            await redis_client.set(
                self.state_key,
                CircuitState.OPEN,
            )

            await redis_client.set(
                self.failure_key,
                self.failure_threshold,
            )

            await redis_client.set(
                self.opened_at_key,
                time.time(),
            )

            await redis_client.delete(
                self.probe_key
            )

            log_event(
                "circuit_state_changed",
                level="WARNING",
                provider=self.provider_name,
                previous_state=CircuitState.HALF_OPEN,
                new_state=CircuitState.OPEN,
            )

            log_event(
                "circuit_recovery_probe_failed",
                level="WARNING",
                provider=self.provider_name,
                state=CircuitState.OPEN,
                failure_count=self.failure_threshold,
            )

            return

        # ----------------------------------------------------
        # CLOSED FAILURE
        # ----------------------------------------------------

        failure_count = (
            await redis_client.incr(
                self.failure_key
            )
        )

        log_event(
            "circuit_failure_recorded",
            level="WARNING",
            provider=self.provider_name,
            state=state,
            failure_count=failure_count,
            failure_threshold=(
                self.failure_threshold
            ),
        )

        # ----------------------------------------------------
        # OPEN CIRCUIT
        # ----------------------------------------------------

        if (
            failure_count
            >= self.failure_threshold
        ):

            await redis_client.set(
                self.state_key,
                CircuitState.OPEN,
            )

            await redis_client.set(
                self.opened_at_key,
                time.time(),
            )

            log_event(
                "circuit_state_changed",
                level="WARNING",
                provider=self.provider_name,
                previous_state=CircuitState.CLOSED,
                new_state=CircuitState.OPEN,
            )

            log_event(
                "circuit_opened",
                level="WARNING",
                provider=self.provider_name,
                failure_count=failure_count,
            )