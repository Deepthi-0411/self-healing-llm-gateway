import time
from dataclasses import dataclass

from app.gateway.request_logger import (
    log_event,
)
from app.infra.redis_client import (
    redis_client,
)


# ============================================================
# RATE LIMIT RESULT
# ============================================================

@dataclass
class RateLimitResult:
    allowed: bool
    limit: int
    current: int
    remaining: int
    retry_after: int


# ============================================================
# REDIS RATE LIMITER
# ============================================================

class RedisRateLimiter:

    def __init__(
        self,
        default_limit=10,
        window_seconds=60,
    ):
        self.default_limit = default_limit
        self.window_seconds = window_seconds

        # ----------------------------------------------------
        # Tenant-specific limits
        # ----------------------------------------------------

        self.tenant_limits = {
            "learning-platform": 10,
            "rate-limit-demo": 3,
        }

        # ----------------------------------------------------
        # Atomic Redis increment script
        # ----------------------------------------------------

        self._increment_script = (
            redis_client.register_script(
                """
                local current = redis.call(
                    'INCR',
                    KEYS[1]
                )

                local ttl = redis.call(
                    'TTL',
                    KEYS[1]
                )

                if current == 1 or ttl < 0 then

                    redis.call(
                        'EXPIRE',
                        KEYS[1],
                        ARGV[1]
                    )

                    ttl = ARGV[1]
                end

                return {
                    current,
                    ttl
                }
                """
            )
        )

    # ========================================================
    # GET LIMIT
    # ========================================================

    def get_limit(
        self,
        tenant,
    ):
        return self.tenant_limits.get(
            tenant,
            self.default_limit,
        )

    # ========================================================
    # CHECK RATE LIMIT
    # ========================================================

    async def check(
        self,
        tenant,
    ):

        limit = self.get_limit(
            tenant
        )

        # ----------------------------------------------------
        # Calculate current fixed-window bucket
        # ----------------------------------------------------

        current_window = (
            time.time()
            // self.window_seconds
        )

        key = (
            f"gateway:rate_limit:"
            f"{tenant}:"
            f"{int(current_window)}"
        )

        # ----------------------------------------------------
        # Atomic increment + TTL
        # ----------------------------------------------------

        result = await self._increment_script(
            keys=[key],
            args=[self.window_seconds],
        )
        log_event(
            "rate_limit_debug",
            debug_key=key,
            debug_result=result,
        )

        

        current = int(
            result[0]
        )

        ttl = int(
            result[1]
        )

        # ----------------------------------------------------
        # Determine allowance
        # ----------------------------------------------------

        allowed = current <= limit

        remaining = max(
            limit - current,
            0,
        )

        retry_after = (
            max(ttl, 0)
            if not allowed
            else 0
        )

        # ----------------------------------------------------
        # Structured log
        # ----------------------------------------------------

        log_event(
            "rate_limit_checked",
            tenant=tenant,
            limit=limit,
            current=current,
            remaining=remaining,
            allowed=allowed,
            retry_after=retry_after,
            window_seconds=self.window_seconds,
        )

        # ----------------------------------------------------
        # Explicit rejection event
        # ----------------------------------------------------

        if not allowed:

            log_event(
                "rate_limit_exceeded",
                level="WARNING",
                tenant=tenant,
                limit=limit,
                current=current,
                remaining=0,
                retry_after=retry_after,
            )

        return RateLimitResult(
            allowed=allowed,
            limit=limit,
            current=current,
            remaining=remaining,
            retry_after=retry_after,
        )


# ============================================================
# GLOBAL RATE LIMITER
# ============================================================

rate_limiter = RedisRateLimiter(
    default_limit=10,
    window_seconds=60,
)