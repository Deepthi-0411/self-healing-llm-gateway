import os

from dotenv import load_dotenv
from redis.asyncio import Redis

from app.gateway.request_logger import log_event


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# REDIS CONFIGURATION
# ============================================================

REDIS_URL = os.getenv(
    "REDIS_URL",
    "redis://localhost:6379/0",
)


# ============================================================
# REDIS CLIENT
# ============================================================

redis_client = Redis.from_url(
    REDIS_URL,
    decode_responses=True,
)


# ============================================================
# REDIS HEALTH CHECK
# ============================================================

async def check_redis() -> bool:
    """
    Check whether Redis is reachable.

    Returns:
        True  -> Redis is available
        False -> Redis is unavailable
    """

    try:

        result = await redis_client.ping()

        healthy = bool(result)

        # ----------------------------------------------------
        # Successful health check
        # ----------------------------------------------------

        log_event(
            "redis_health_check",
            redis_status=(
                "connected"
                if healthy
                else "unhealthy"
            ),
        )

        return healthy

    except Exception as error:

        # ----------------------------------------------------
        # Failed health check
        # ----------------------------------------------------

        log_event(
            "redis_health_check_failed",
            level="ERROR",
            error_type=type(error).__name__,
            error_message=str(error),
        )

        return False


# ============================================================
# REDIS SHUTDOWN
# ============================================================

async def close_redis() -> None:
    """
    Close the asynchronous Redis connection.
    """

    try:

        await redis_client.aclose()

        log_event(
            "redis_connection_closed",
        )

    except Exception as error:

        log_event(
            "redis_connection_close_failed",
            level="ERROR",
            error_type=type(error).__name__,
            error_message=str(error),
        )