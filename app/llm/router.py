import asyncio
import os
import time

from app.gateway.errors import (
    classify_error,
)
from app.gateway.provider_health import (
    ProviderHealth,
)
from app.gateway.request_logger import (
    log_event,
)
from app.gateway.retry import (
    call_with_retry,
)
from app.llm.client import (
    call_cloudflare,
    call_cohere,
    call_gemini,
)
from app.llm.models import (
    get_provider_chain_for_tier,
)
from app.llm.tiering import (
    classify_request,
)

from app.observability.metrics import (
    gateway_provider_failures_total,
    gateway_provider_latency_seconds,
)


# ============================================================
# PROVIDER HEALTH
# ============================================================

provider_health = ProviderHealth()


# ============================================================
# DEVELOPMENT FAILURE INJECTION
# ============================================================

class RateLimitError(Exception):
    """
    Development-only simulated rate-limit error.
    """
    pass


# ============================================================
# GEMINI WITH FAILURE INJECTION
# ============================================================

async def call_gemini_with_injection(
    messages,
    model="gemini/gemini-3.6-flash",
    temperature=None,
    max_tokens=None,
):
    probe_delay = float(
        os.getenv(
            "GEMINI_PROBE_DELAY_SECONDS",
            "0",
        )
    )

    if probe_delay > 0:

        log_event(
            "gemini_probe_delay",
            delay_seconds=probe_delay,
        )

        await asyncio.sleep(
            probe_delay
        )

    force_gemini_failure = (
        os.getenv(
            "FORCE_GEMINI_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    if force_gemini_failure:

        log_event(
            "gemini_failure_injected",
            level="WARNING",
        )

        raise RuntimeError(
            "Simulated Gemini failure"
        )

    force_rate_limit_failure = (
        os.getenv(
            "FORCE_GEMINI_RATE_LIMIT_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    if force_rate_limit_failure:

        log_event(
            "gemini_rate_limit_injected",
            level="WARNING",
        )

        raise RateLimitError(
            "Simulated Gemini rate limit"
        )

    return await call_gemini(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ============================================================
# CLOUDFLARE WITH FAILURE INJECTION
# ============================================================

async def call_cloudflare_with_injection(
    messages,
    model=(
        "cloudflare/"
        "@cf/meta/llama-3.1-8b-instruct-fp8"
    ),
    temperature=None,
    max_tokens=None,
):
    force_cloudflare_failure = (
        os.getenv(
            "FORCE_CLOUDFLARE_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    if force_cloudflare_failure:

        log_event(
            "cloudflare_failure_injected",
            level="WARNING",
        )

        raise RuntimeError(
            "Simulated Cloudflare failure"
        )

    return await call_cloudflare(
        messages=messages,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )


# ============================================================
# PROVIDER DISPATCH
# ============================================================

async def call_provider(
    provider,
    model,
    messages,
    temperature=None,
    max_tokens=None,
):
    """
    Dispatch the request to one of the three active providers:

    Gemini
    Cloudflare Workers AI
    Cohere
    """

    if provider == "gemini":

        return await call_gemini_with_injection(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "cloudflare":

        return await call_cloudflare_with_injection(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if provider == "cohere":

        return await call_cohere(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(
        f"Unsupported provider: {provider}"
    )


# ============================================================
# PROVIDER ROUTER
# ============================================================

async def call_with_fallback(
    messages,
    temperature=None,
    max_tokens=None,
    tier=None,
):
    """
    Execute the provider chain with:

    1. Redis circuit-breaker checks
    2. Retry / exponential backoff
    3. Provider health recording
    4. Provider fallback
    5. Provider latency telemetry
    6. Provider failure telemetry

    Provider health metrics are maintained by ProviderHealth.
    """

    if tier is None:
        tier = classify_request(
            messages
        )

    log_event(
        "provider_routing_started",
        tier=tier.value,
    )

    provider_chain = (
        get_provider_chain_for_tier(
            tier
        )
    )

    log_event(
        "provider_chain_selected",
        tier=tier.value,
        provider_chain=[
            {
                "provider": target["provider"],
                "model": target["model"],
            }
            for target in provider_chain
        ],
    )

    last_error = None

    # ========================================================
    # PROVIDER LOOP
    # ========================================================

    for index, target in enumerate(
        provider_chain,
        start=1,
    ):

        provider = target[
            "provider"
        ]

        model = target[
            "model"
        ]

        # ----------------------------------------------------
        # Log provider attempt
        # ----------------------------------------------------

        log_event(
            "provider_attempt_started",
            attempt=index,
            total_providers=len(
                provider_chain
            ),
            provider=provider,
            model=model,
            tier=tier.value,
        )

        # ----------------------------------------------------
        # Circuit breaker / provider health check
        # ----------------------------------------------------

        try:

            can_execute = (
                await provider_health.can_execute(
                    provider
                )
            )

        except Exception as error:

            last_error = error

            log_event(
                "provider_health_check_failed",
                level="ERROR",
                provider=provider,
                model=model,
                tier=tier.value,
                error_type=type(
                    error
                ).__name__,
                error_message=str(
                    error
                ),
            )

            continue

        # ----------------------------------------------------
        # Provider blocked by circuit breaker
        # ----------------------------------------------------

        if not can_execute:

            log_event(
                "provider_skipped_circuit_open",
                level="WARNING",
                provider=provider,
                model=model,
                tier=tier.value,
            )

            continue

        # ----------------------------------------------------
        # Provider call wrapper
        # ----------------------------------------------------

        async def provider_call(
            messages,
            temperature=None,
            max_tokens=None,
            provider=provider,
            model=model,
        ):
            return await call_provider(
                provider=provider,
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

        # ----------------------------------------------------
        # Start provider latency timer
        # ----------------------------------------------------

        provider_start = time.perf_counter()

        # ----------------------------------------------------
        # Execute with retry
        # ----------------------------------------------------

        try:

            result = await call_with_retry(
                call_function=provider_call,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )

            # ------------------------------------------------
            # Provider success
            # ------------------------------------------------

            await provider_health.record_success(
                provider
            )

            log_event(
                "provider_request_succeeded",
                provider=provider,
                model=model,
                tier=tier.value,
                attempt=index,
            )

            return result

        except Exception as error:

            last_error = error

            # ------------------------------------------------
            # Classify provider failure
            # ------------------------------------------------

            error_category = classify_error(
                error
            )

            # ------------------------------------------------
            # Record provider failure in circuit breaker
            # ------------------------------------------------

            try:

                await provider_health.record_failure(
                    provider
                )

            except Exception as health_error:

                log_event(
                    "provider_failure_recording_failed",
                    level="ERROR",
                    provider=provider,
                    model=model,
                    tier=tier.value,
                    error_type=type(
                        health_error
                    ).__name__,
                    error_message=str(
                        health_error
                    ),
                )

            # ------------------------------------------------
            # Record provider failure metric
            #
            # One increment represents one provider attempt
            # after the retry policy has been exhausted.
            # ------------------------------------------------

            try:

                gateway_provider_failures_total.labels(
                    provider=provider,
                    error_category=(
                        error_category.value
                    ),
                ).inc()

            except Exception as metric_error:

                log_event(
                    "provider_failure_metric_recording_failed",
                    level="ERROR",
                    provider=provider,
                    model=model,
                    tier=tier.value,
                    error_type=type(
                        metric_error
                    ).__name__,
                    error_message=str(
                        metric_error
                    ),
                )

            # ------------------------------------------------
            # Log provider failure safely
            # ------------------------------------------------

            log_event(
                "provider_request_failed",
                level="WARNING",
                provider=provider,
                model=model,
                tier=tier.value,
                attempt=index,
                error_type=type(
                    error
                ).__name__,
                error_message=str(
                    error
                ),
                error_category=(
                    error_category.value
                ),
            )

            # ------------------------------------------------
            # Continue to next provider
            # ------------------------------------------------

            log_event(
                "provider_fallback_started",
                provider=provider,
                model=model,
                tier=tier.value,
                next_attempt=index + 1,
            )

        finally:

            # ------------------------------------------------
            # Record provider latency
            # ------------------------------------------------

            provider_latency = (
                time.perf_counter()
                - provider_start
            )

            try:

                gateway_provider_latency_seconds.labels(
                    provider=provider,
                ).observe(
                    provider_latency
                )

            except Exception as metric_error:

                log_event(
                    "provider_latency_metric_recording_failed",
                    level="ERROR",
                    provider=provider,
                    model=model,
                    tier=tier.value,
                    error_type=type(
                        metric_error
                    ).__name__,
                    error_message=str(
                        metric_error
                    ),
                )

    # ========================================================
    # ALL PROVIDERS FAILED
    # ========================================================

    log_event(
        "all_providers_failed",
        level="ERROR",
        tier=tier.value,
        error_type=(
            type(last_error).__name__
            if last_error is not None
            else "Unknown"
        ),
        error_message=(
            str(last_error)
            if last_error is not None
            else "No provider error available"
        ),
    )

    if last_error is not None:

        raise RuntimeError(
            "All configured LLM providers failed."
        ) from last_error

    raise RuntimeError(
        "All configured LLM providers are unavailable."
    )