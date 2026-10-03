import os
from typing import Any

from dotenv import load_dotenv

from app.cache.embeddings import embed_text
from app.cache.semantic_cache import semantic_cache
from app.gateway.request_logger import log_event


load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

def is_semantic_cache_enabled() -> bool:
    return (
        os.getenv(
            "SEMANTIC_CACHE_ENABLED",
            "true",
        ).lower()
        == "true"
    )


def should_force_lookup_failure() -> bool:
    return (
        os.getenv(
            "FORCE_SEMANTIC_LOOKUP_FAILURE",
            "false",
        ).lower()
        == "true"
    )


def should_force_store_failure() -> bool:
    return (
        os.getenv(
            "FORCE_SEMANTIC_STORE_FAILURE",
            "false",
        ).lower()
        == "true"
    )


# ============================================================
# SAFE SEMANTIC CACHE LOOKUP
# ============================================================

async def safe_semantic_lookup(
    tenant: str,
    feature: str,
    requested_model: str,
    tier: str,
    cache_text: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> dict[str, Any] | None:
    """
    Failure-safe semantic cache lookup.

    Any embedding or Redis failure is caught here and converted
    into a normal cache MISS so the main LLM request can continue.

    Important:
        cache_text, embeddings, prompts, and responses are never
        written to the structured logs.
    """

    # --------------------------------------------------------
    # Semantic cache disabled
    # --------------------------------------------------------

    if not is_semantic_cache_enabled():

        log_event(
            "semantic_cache_disabled",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
        )

        return None

    # --------------------------------------------------------
    # Lookup started
    # --------------------------------------------------------

    log_event(
        "semantic_cache_lookup_started",
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
        tier=tier,
    )

    try:

        # ----------------------------------------------------
        # Failure injection
        # ----------------------------------------------------

        if should_force_lookup_failure():

            log_event(
                "semantic_cache_lookup_failure_injected",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
            )

            raise RuntimeError(
                "Simulated semantic cache lookup failure"
            )

        # ----------------------------------------------------
        # Create query embedding using Cohere
        # ----------------------------------------------------

        query_vector = await embed_text(
            text=cache_text,
            input_type="search_query",
        )

        # ----------------------------------------------------
        # Search Redis semantic cache
        # ----------------------------------------------------

        result = await semantic_cache.search(
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            query_vector=query_vector,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # ----------------------------------------------------
        # Semantic cache MISS
        # ----------------------------------------------------

        if result is None:

            log_event(
                "semantic_cache_miss",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
            )

            return None

        # ----------------------------------------------------
        # Semantic cache HIT
        # ----------------------------------------------------

        log_event(
            "semantic_cache_hit",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            actual_provider=result.get(
                "actual_provider"
            ),
            actual_model=result.get(
                "actual_model"
            ),
            similarity=result.get(
                "similarity"
            ),
        )

        return result

    # --------------------------------------------------------
    # Fail-open behavior
    # --------------------------------------------------------

    except Exception as error:

        log_event(
            "semantic_cache_lookup_failed",
            level="WARNING",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            error_type=type(error).__name__,
            error_message=str(error),
        )

        log_event(
            "semantic_cache_lookup_fail_open",
            level="WARNING",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
        )

        return None


# ============================================================
# SAFE SEMANTIC CACHE STORE
# ============================================================

async def safe_semantic_store(
    tenant: str,
    feature: str,
    requested_model: str,
    tier: str,
    cache_text: str,
    response: Any,
    actual_provider: str,
    actual_model: str,
    temperature: float | None = None,
    max_tokens: int | None = None,
) -> bool:
    """
    Failure-safe semantic cache storage.

    Any embedding or Redis failure is caught here.

    The already-generated LLM response is still considered
    successful even when semantic caching fails.

    Returns:
        True  -> semantic cache stored successfully
        False -> semantic cache was not stored
    """

    # --------------------------------------------------------
    # Semantic cache disabled
    # --------------------------------------------------------

    if not is_semantic_cache_enabled():

        log_event(
            "semantic_cache_disabled",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
        )

        return False

    # --------------------------------------------------------
    # Store started
    # --------------------------------------------------------

    log_event(
        "semantic_cache_store_started",
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
        tier=tier,
        actual_provider=actual_provider,
        actual_model=actual_model,
    )

    try:

        # ----------------------------------------------------
        # Failure injection
        # ----------------------------------------------------

        if should_force_store_failure():

            log_event(
                "semantic_cache_store_failure_injected",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
            )

            raise RuntimeError(
                "Simulated semantic cache store failure"
            )

        # ----------------------------------------------------
        # Create document embedding using Cohere
        # ----------------------------------------------------

        document_vector = await embed_text(
            text=cache_text,
            input_type="search_document",
        )

        # ----------------------------------------------------
        # Store response in Redis
        # ----------------------------------------------------

        await semantic_cache.set(
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            cache_text=cache_text,
            document_vector=document_vector,
            response=response,
            actual_provider=actual_provider,
            actual_model=actual_model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # ----------------------------------------------------
        # Store successful
        # ----------------------------------------------------

        log_event(
            "semantic_cache_stored",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            actual_provider=actual_provider,
            actual_model=actual_model,
        )

        return True

    # --------------------------------------------------------
    # Fail-open behavior
    # --------------------------------------------------------

    except Exception as error:

        log_event(
            "semantic_cache_store_failed",
            level="WARNING",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            actual_provider=actual_provider,
            actual_model=actual_model,
            error_type=type(error).__name__,
            error_message=str(error),
        )

        log_event(
            "semantic_cache_store_fail_open",
            level="WARNING",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            actual_provider=actual_provider,
            actual_model=actual_model,
        )

        return False