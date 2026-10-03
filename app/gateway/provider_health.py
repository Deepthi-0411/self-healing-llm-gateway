from app.gateway.redis_circuit_breaker import (
    RedisCircuitBreaker,
)

from app.observability.metrics import (
    gateway_provider_health,
)


class ProviderHealth:

    def __init__(self):

        self.providers = {

            "gemini": RedisCircuitBreaker(
                provider_name="gemini",
                failure_threshold=3,
                recovery_timeout=10,
            ),

            "cloudflare": RedisCircuitBreaker(
                provider_name="cloudflare",
                failure_threshold=3,
                recovery_timeout=10,
            ),

            "cohere": RedisCircuitBreaker(
                provider_name="cohere",
                failure_threshold=3,
                recovery_timeout=10,
            ),
        }

        # ----------------------------------------------------
        # Initialize provider health metrics
        #
        # All breakers start in CLOSED state for a new
        # provider-health object, so initialize the metric
        # as available. The metric is subsequently corrected
        # whenever the gateway checks the breaker state.
        # ----------------------------------------------------

        for provider in self.providers:

            gateway_provider_health.labels(
                provider=provider,
            ).set(1)

    # ========================================================
    # GET BREAKER
    # ========================================================

    def get_breaker(
        self,
        provider: str,
    ) -> RedisCircuitBreaker:

        if provider not in self.providers:

            raise ValueError(
                f"Unknown provider: {provider}"
            )

        return self.providers[provider]

    # ========================================================
    # CAN EXECUTE
    # ========================================================

    async def can_execute(
        self,
        provider: str,
    ) -> bool:

        breaker = self.get_breaker(
            provider
        )

        can_execute = await breaker.can_execute()

        # ----------------------------------------------------
        # Update health metric from the actual breaker decision
        #
        # 1 = provider currently allowed to execute
        # 0 = provider currently blocked
        # ----------------------------------------------------

        gateway_provider_health.labels(
            provider=provider,
        ).set(
            1 if can_execute else 0
        )

        return can_execute

    # ========================================================
    # RECORD SUCCESS
    # ========================================================

    async def record_success(
        self,
        provider: str,
    ):

        await self.get_breaker(
            provider
        ).record_success()

        # Successful execution means the provider is healthy.
        gateway_provider_health.labels(
            provider=provider,
        ).set(1)

    # ========================================================
    # RECORD FAILURE
    # ========================================================

    async def record_failure(
        self,
        provider: str,
    ):

        await self.get_breaker(
            provider
        ).record_failure()

        # ----------------------------------------------------
        # Do NOT immediately set the metric to 0 here.
        #
        # A single failure does not necessarily mean the
        # provider is unavailable. The Redis circuit breaker
        # may still be CLOSED and allow further requests.
        #
        # The next can_execute() call publishes the actual
        # breaker decision.
        # ----------------------------------------------------