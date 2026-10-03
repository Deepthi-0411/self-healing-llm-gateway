import hashlib
import json
import os
from typing import Any

from dotenv import load_dotenv

from app.gateway.request_logger import log_event
from app.infra.redis_client import redis_client


load_dotenv()


# ============================================================
# CACHE CONFIGURATION
# ============================================================

CACHE_TTL_SECONDS = int(
    os.getenv(
        "CACHE_TTL_SECONDS",
        "300",
    )
)


# ============================================================
# REDIS RESPONSE CACHE
# ============================================================

class RedisResponseCache:
    """
    Redis-backed exact-request response cache.

    The cache key is generated from:

        tenant
        feature
        requested model
        messages
        temperature
        max_tokens

    request_id is intentionally NOT included because the same
    logical request with a different request ID should be
    eligible for the same cached response.
    """

    def __init__(
        self,
        ttl_seconds: int = CACHE_TTL_SECONDS,
    ):
        self.ttl_seconds = ttl_seconds

    # ========================================================
    # BUILD CACHE KEY
    # ========================================================

    def build_key(
        self,
        tenant: str,
        feature: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> str:
        """
        Build a deterministic cache key.

        The actual prompt is hashed rather than stored directly
        in the Redis key.
        """

        cache_payload = {
            "tenant": tenant,
            "feature": feature,
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        canonical_payload = json.dumps(
            cache_payload,
            sort_keys=True,
            separators=(
                ",",
                ":",
            ),
            ensure_ascii=False,
        )

        digest = hashlib.sha256(
            canonical_payload.encode(
                "utf-8"
            )
        ).hexdigest()

        return (
            f"gateway:cache:v1:{digest}"
        )

    # ========================================================
    # GET
    # ========================================================

    async def get(
        self,
        tenant: str,
        feature: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> Any | None:
        """
        Return cached response if present.

        Returns:
            Parsed cached response or None.
        """

        key = self.build_key(
            tenant=tenant,
            feature=feature,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # ----------------------------------------------------
        # Redis lookup
        # ----------------------------------------------------

        log_event(
            "exact_cache_lookup",
            tenant=tenant,
            feature=feature,
            requested_model=model,
        )

        raw_value = await redis_client.get(
            key
        )

        # ----------------------------------------------------
        # CACHE MISS
        # ----------------------------------------------------

        if raw_value is None:

            log_event(
                "exact_cache_miss",
                tenant=tenant,
                feature=feature,
                requested_model=model,
            )

            return None

        # ----------------------------------------------------
        # CACHE ENTRY FOUND
        # ----------------------------------------------------

        try:

            response = json.loads(
                raw_value
            )

        except json.JSONDecodeError:

            log_event(
                "exact_cache_invalid_entry",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=model,
            )

            await redis_client.delete(
                key
            )

            log_event(
                "exact_cache_invalid_entry_deleted",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=model,
            )

            return None

        # ----------------------------------------------------
        # CACHE HIT
        # ----------------------------------------------------

        log_event(
            "exact_cache_hit",
            tenant=tenant,
            feature=feature,
            requested_model=model,
        )

        return response

    # ========================================================
    # SET
    # ========================================================

    async def set(
        self,
        tenant: str,
        feature: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
        response: Any,
    ) -> None:
        """
        Store a successful response in Redis.
        """

        key = self.build_key(
            tenant=tenant,
            feature=feature,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        serialized_response = json.dumps(
            response,
            ensure_ascii=False,
            default=str,
        )

        await redis_client.set(
            key,
            serialized_response,
            ex=self.ttl_seconds,
        )

        # ----------------------------------------------------
        # CACHE STORED
        # ----------------------------------------------------

        log_event(
            "exact_cache_stored",
            tenant=tenant,
            feature=feature,
            requested_model=model,
            ttl_seconds=self.ttl_seconds,
        )

    # ========================================================
    # DELETE
    # ========================================================

    async def delete(
        self,
        tenant: str,
        feature: str,
        model: str,
        messages: list[dict[str, str]],
        temperature: float | None,
        max_tokens: int | None,
    ) -> None:
        """
        Delete a specific cached response.
        """

        key = self.build_key(
            tenant=tenant,
            feature=feature,
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        await redis_client.delete(
            key
        )

        # ----------------------------------------------------
        # CACHE DELETED
        # ----------------------------------------------------

        log_event(
            "exact_cache_deleted",
            tenant=tenant,
            feature=feature,
            requested_model=model,
        )


# ============================================================
# GLOBAL CACHE
# ============================================================

response_cache = RedisResponseCache(
    ttl_seconds=CACHE_TTL_SECONDS,
)