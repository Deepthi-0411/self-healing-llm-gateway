import os
import time
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app.gateway.auth import authenticate_request

from typing import Literal

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    generate_latest,
)

from app.cache.response_cache import (
    response_cache,
)

from app.cache.semantic_cache import (
    build_cache_text,
)

from app.cache.semantic_cache_service import (
    safe_semantic_lookup,
    safe_semantic_store,
)

from app.gateway.budget import (
    budget_manager,
)

from app.gateway.rate_limiter import (
    rate_limiter,
)

from app.gateway.request_logger import (
    log_event,
)

from app.infra.redis_client import (
    check_redis,
    close_redis,
)

from app.llm.router import (
    call_with_fallback,
)

from app.llm.tiering import (
    classify_request,
)

from app.observability.metrics import (
    gateway_http_requests_total,
    gateway_request_latency_seconds,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()

APP_ENV = os.getenv(
    "APP_ENV",
    "development",
).lower()

# ============================================================
# REQUEST MODELS
# ============================================================

class Message(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(
        min_length=1,
    )


class RequestMetadata(BaseModel):
    tenant: str = Field(
        min_length=1,
    )

    feature: str = Field(
        min_length=1,
    )

    request_id: str = Field(
        min_length=1,
    )


class ChatCompletionRequest(BaseModel):
    model: str = "auto"

    messages: list[Message] = Field(
        min_length=1,
    )

    temperature: float | None = None

    max_tokens: int | None = Field(
        default=None,
        gt=0,
    )

    metadata: RequestMetadata


class FailureInjectionRequest(BaseModel):
    enabled: bool

    probe_delay_seconds: float = Field(
        default=0,
        ge=0,
        le=60,
    )


# ============================================================
# APPLICATION LIFESPAN
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    # ========================================================
    # PROVIDER CREDENTIALS
    # ========================================================

    gemini_key = os.getenv(
        "GEMINI_API_KEY",
    )

    cloudflare_token = os.getenv(
        "CLOUDFLARE_API_TOKEN",
    )

    cloudflare_account_id = os.getenv(
        "CLOUDFLARE_ACCOUNT_ID",
    )

    cohere_key = os.getenv(
        "COHERE_API_KEY",
    )

    # ========================================================
    # FAILURE INJECTION
    # ========================================================

    force_gemini_failure = (
        os.getenv(
            "FORCE_GEMINI_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    force_rate_limit_failure = (
        os.getenv(
            "FORCE_GEMINI_RATE_LIMIT_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    force_cloudflare_failure = (
        os.getenv(
            "FORCE_CLOUDFLARE_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    semantic_cache_enabled = (
        os.getenv(
            "SEMANTIC_CACHE_ENABLED",
            "true",
        ).lower()
        == "true"
    )

    force_semantic_lookup_failure = (
        os.getenv(
            "FORCE_SEMANTIC_LOOKUP_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    force_semantic_store_failure = (
        os.getenv(
            "FORCE_SEMANTIC_STORE_FAILURE",
            "false",
        ).lower()
        == "true"
    )

    if APP_ENV == "production" and any(
        [
            force_gemini_failure,
            force_rate_limit_failure,
            force_cloudflare_failure,
            force_semantic_lookup_failure,
            force_semantic_store_failure,
        ]
    ):
        raise RuntimeError(
            "Failure injection must be disabled in production."
        )

    # ========================================================
    # REDIS
    # ========================================================

    redis_healthy = await check_redis()

    if not redis_healthy:

        log_event(
            "gateway_startup_failed",
            level="ERROR",
            redis_status="unavailable",
        )

        raise RuntimeError(
            "Redis is unavailable. "
            "The gateway cannot start."
        )

    # ========================================================
    # STRUCTURED STARTUP EVENT
    # ========================================================

    log_event(
        "gateway_startup",
        providers=[
            "gemini",
            "cloudflare",
            "cohere",
        ],
        gemini_credentials=bool(
            gemini_key
        ),
        cloudflare_token_configured=bool(
            cloudflare_token
        ),
        cloudflare_account_configured=bool(
            cloudflare_account_id
        ),
        cohere_credentials=bool(
            cohere_key
        ),
        redis_status="connected",
        rate_limiter="enabled",
        tenant_budget="enabled",
        circuit_breaker="redis-backed",
        exact_response_cache="enabled",
        semantic_cache=(
            "enabled"
            if semantic_cache_enabled
            else "disabled"
        ),
        cache_ttl_seconds=(
            response_cache.ttl_seconds
        ),
        forced_gemini_failure=(
            force_gemini_failure
        ),
        forced_gemini_rate_limit_failure=(
            force_rate_limit_failure
        ),
        forced_cloudflare_failure=(
            force_cloudflare_failure
        ),
        forced_semantic_lookup_failure=(
            force_semantic_lookup_failure
        ),
        forced_semantic_store_failure=(
            force_semantic_store_failure
        ),
    )

    # ========================================================
    # APPLICATION RUNNING
    # ========================================================

    yield

    # ========================================================
    # SHUTDOWN
    # ========================================================

    try:

        await close_redis()

        log_event(
            "gateway_shutdown",
            redis_status="closed",
        )

    except Exception as error:

        log_event(
            "gateway_shutdown_failed",
            level="ERROR",
            error_type=type(error).__name__,
            error_message=str(error),
        )


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Self-Healing LLM Gateway",
    version="0.6.0",
    lifespan=lifespan,
)

# ============================================================
# PROMETHEUS HTTP METRICS
# ============================================================

@app.middleware("http")
async def prometheus_http_metrics(
    request: Request,
    call_next,
):
    # Do not count Prometheus scraping itself as a gateway
    # application request.
    if request.url.path == "/metrics":
        return await call_next(request)

    start_time = time.perf_counter()
    status_code = 500

    try:

        response = await call_next(request)
        status_code = response.status_code

        return response

    finally:

        latency = (
            time.perf_counter()
            - start_time
        )

        gateway_http_requests_total.labels(
            method=request.method,
            path=request.url.path,
            status=str(status_code),
        ).inc()

        gateway_request_latency_seconds.labels(
            path=request.url.path,
        ).observe(
            latency
        )

# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "service": "Self-Healing LLM Gateway",
        "status": "running",
        "providers": [
            "gemini",
            "cloudflare",
            "cohere",
        ],
        "redis": "enabled",
        "rate_limiter": "enabled",
        "budget": "enabled",
        "circuit_breaker": "redis-backed",
        "response_cache": "enabled",
        "semantic_cache": "enabled",
    }

# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    redis_healthy = await check_redis()

    if redis_healthy:

        return {
            "status": "healthy",
            "redis": "connected",
            "rate_limiter": "enabled",
            "budget": "enabled",
            "circuit_breaker": "redis-backed",
            "response_cache": "enabled",
            "semantic_cache": "enabled",
        }

    raise HTTPException(
        status_code=503,
        detail={
            "status": "unhealthy",
            "redis": "unavailable",
        },
    )

# ============================================================
# PROMETHEUS METRICS
# ============================================================

@app.get("/metrics")
async def metrics():

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
    )

# ============================================================
# FAILURE INJECTION
# ============================================================

@app.post(
    "/debug/failure-injection"
)
async def failure_injection(
    request: FailureInjectionRequest,
):
    if APP_ENV == "production":
        raise HTTPException(
            status_code=404,
            detail="Not found.",
        )

    os.environ[
        "FORCE_GEMINI_FAILURE"
    ] = (
        "true"
        if request.enabled
        else "false"
    )

    os.environ[
        "GEMINI_PROBE_DELAY_SECONDS"
    ] = str(
        request.probe_delay_seconds
    )

    log_event(
        "failure_injection_updated",
        level="WARNING",
        force_gemini_failure=(
            request.enabled
        ),
        probe_delay_seconds=(
            request.probe_delay_seconds
        ),
    )

    return {
        "force_gemini_failure": (
            request.enabled
        ),
        "probe_delay_seconds": (
            request.probe_delay_seconds
        ),
    }

# ============================================================
# CHAT COMPLETIONS
# ============================================================

@app.post(
    "/v1/chat/completions"
)
async def chat_completions(
    request: ChatCompletionRequest,
    response: Response,
    authenticated_tenant: str = Depends(
        authenticate_request
    ),
):

    # ========================================================
    # AUTHORITATIVE TENANT
    # ========================================================

    tenant = authenticated_tenant

    # ========================================================
    # TENANT ISOLATION CHECK
    # ========================================================

    if request.metadata.tenant != tenant:

        log_event(
            "request_rejected_tenant_mismatch",
            level="WARNING",
            request_id=(
                request.metadata.request_id
            ),
            authenticated_tenant=tenant,
            requested_tenant=(
                request.metadata.tenant
            ),
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
        )

        raise HTTPException(
            status_code=403,
            detail={
                "error": "tenant_mismatch",
                "request_id": (
                    request.metadata.request_id
                ),
            },
        )

    # ========================================================
    # CONVERT MESSAGES
    # ========================================================

    messages = [
        {
            "role": message.role,
            "content": message.content,
        }
        for message in request.messages
    ]

    # ========================================================
    # REQUEST STARTED
    # ========================================================

    log_event(
        "request_started",
        request_id=(
            request.metadata.request_id
        ),
        tenant=tenant,
        feature=(
            request.metadata.feature
        ),
        requested_model=request.model,
    )

    # ========================================================
    # 1. RATE LIMIT CHECK
    # ========================================================

    rate_limit_result = await rate_limiter.check(
        tenant
    )

    if not rate_limit_result.allowed:

        log_event(
            "request_rejected_rate_limit",
            level="WARNING",
            request_id=(
                request.metadata.request_id
            ),
            tenant=tenant,
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
            limit=(
                rate_limit_result.limit
            ),
            current=(
                rate_limit_result.current
            ),
            remaining=(
                rate_limit_result.remaining
            ),
            retry_after=(
                rate_limit_result.retry_after
            ),
        )

        raise HTTPException(
            status_code=429,
            headers={
                "Retry-After": str(
                    rate_limit_result.retry_after
                ),
                "X-RateLimit-Limit": str(
                    rate_limit_result.limit
                ),
                "X-RateLimit-Remaining": "0",
                "X-Cache": "BYPASS",
            },
            detail={
                "error": "rate_limit_exceeded",
                "tenant": tenant,
                "limit": (
                    rate_limit_result.limit
                ),
                "current": (
                    rate_limit_result.current
                ),
                "remaining": 0,
                "retry_after": (
                    rate_limit_result.retry_after
                ),
                "request_id": (
                    request.metadata.request_id
                ),
            },
        )

    # ========================================================
    # RATE LIMIT HEADERS
    # ========================================================

    response.headers[
        "X-RateLimit-Limit"
    ] = str(
        rate_limit_result.limit
    )

    response.headers[
        "X-RateLimit-Remaining"
    ] = str(
        rate_limit_result.remaining
    )

    # ========================================================
    # 2. REQUEST TIERING
    # ========================================================

    tier = classify_request(
        messages
    )

    log_event(
        "request_tier_classified",
        request_id=(
            request.metadata.request_id
        ),
        tenant=tenant,
        feature=(
            request.metadata.feature
        ),
        requested_model=request.model,
        tier=tier.value,
    )

    # ========================================================
    # BUILD SEMANTIC CACHE TEXT
    # ========================================================

    cache_text = build_cache_text(
        messages
    )

    # ========================================================
    # 3. EXACT CACHE LOOKUP
    # ========================================================

    cached_result = await response_cache.get(
        tenant=tenant,
        feature=request.metadata.feature,
        model=request.model,
        messages=messages,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    # --------------------------------------------------------
    # EXACT CACHE HIT
    # --------------------------------------------------------

    if cached_result is not None:

        log_event(
            "request_completed_from_exact_cache",
            request_id=(
                request.metadata.request_id
            ),
            tenant=tenant,
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
            tier=tier.value,
            cache_status="exact_hit",
        )

        response.headers[
            "X-Cache"
        ] = "HIT"

        return cached_result

    # --------------------------------------------------------
    # EXACT CACHE MISS
    # --------------------------------------------------------

    response.headers[
        "X-Cache"
    ] = "MISS"

    # ========================================================
    # 4. FAILURE-SAFE SEMANTIC CACHE LOOKUP
    # ========================================================

    semantic_result = await safe_semantic_lookup(
        tenant=tenant,
        feature=request.metadata.feature,
        requested_model=request.model,
        tier=tier.value,
        cache_text=cache_text,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
    )

    # --------------------------------------------------------
    # SEMANTIC CACHE HIT
    # --------------------------------------------------------

    if semantic_result is not None:

        log_event(
            "request_completed_from_semantic_cache",
            request_id=(
                request.metadata.request_id
            ),
            tenant=tenant,
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
            tier=tier.value,
            cache_status="semantic_hit",
            similarity=(
                semantic_result.get(
                    "similarity"
                )
            ),
            distance=(
                semantic_result.get(
                    "distance"
                )
            ),
        )

        response.headers[
            "X-Cache"
        ] = "SEMANTIC-HIT"

        return semantic_result[
            "response"
        ]

    # --------------------------------------------------------
    # SEMANTIC MISS OR SAFE FAILURE
    # --------------------------------------------------------

    log_event(
        "semantic_cache_not_used",
        request_id=(
            request.metadata.request_id
        ),
        tenant=tenant,
        feature=(
            request.metadata.feature
        ),
        requested_model=request.model,
        tier=tier.value,
    )

    # ========================================================
    # 5. TENANT BUDGET
    # ========================================================

    budget_result = (
        await budget_manager.check_and_consume(
            tenant=tenant,
            tier=tier,
        )
    )

    if not budget_result.allowed:

        log_event(
            "request_rejected_budget",
            level="WARNING",
            request_id=(
                request.metadata.request_id
            ),
            tenant=tenant,
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
            tier=tier.value,
            limit=(
                budget_result.limit
            ),
            used=(
                budget_result.used
            ),
            remaining=(
                budget_result.remaining
            ),
            requested=(
                budget_result.requested
            ),
            reset_after=(
                budget_result.reset_after
            ),
        )

        raise HTTPException(
            status_code=402,
            headers={
                "X-Budget-Limit": str(
                    budget_result.limit
                ),
                "X-Budget-Used": str(
                    budget_result.used
                ),
                "X-Budget-Remaining": "0",
                "X-Budget-Requested": str(
                    budget_result.requested
                ),
                "X-Cache": "MISS",
            },
            detail={
                "error": "budget_exceeded",
                "tenant": tenant,
                "limit": (
                    budget_result.limit
                ),
                "used": (
                    budget_result.used
                ),
                "remaining": (
                    budget_result.remaining
                ),
                "requested": (
                    budget_result.requested
                ),
                "reset_after": (
                    budget_result.reset_after
                ),
                "request_id": (
                    request.metadata.request_id
                ),
            },
        )

    # ========================================================
    # BUDGET HEADERS
    # ========================================================

    response.headers[
        "X-Budget-Limit"
    ] = str(
        budget_result.limit
    )

    response.headers[
        "X-Budget-Used"
    ] = str(
        budget_result.used
    )

    response.headers[
        "X-Budget-Remaining"
    ] = str(
        budget_result.remaining
    )

    response.headers[
        "X-Budget-Requested"
    ] = str(
        budget_result.requested
    )

    # ========================================================
    # 6. LLM ROUTER
    # ========================================================

    try:

        result = await call_with_fallback(
            messages=messages,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            tier=tier,
        )

        # ====================================================
        # CONVERT LITELLM RESPONSE
        # ====================================================

        if hasattr(
            result,
            "model_dump",
        ):

            response_payload = (
                result.model_dump()
            )

        elif hasattr(
            result,
            "dict",
        ):

            response_payload = (
                result.dict()
            )

        else:

            response_payload = result

        # ====================================================
        # 7. STORE SUCCESSFUL RESPONSE
        # ====================================================

        try:

            await response_cache.set(
                tenant=tenant,
                feature=request.metadata.feature,
                model=request.model,
                messages=messages,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
                response=response_payload,
            )

        except Exception as cache_error:

            log_event(
                "exact_cache_store_failed_safely",
                level="WARNING",
                request_id=(
                    request.metadata.request_id
                ),
                tenant=tenant,
                feature=(
                    request.metadata.feature
                ),
                requested_model=request.model,
                error_type=(
                    type(cache_error).__name__
                ),
                error_message=str(
                    cache_error
                ),
            )

        # ====================================================
        # 8. SEMANTIC CACHE STORE
        # ====================================================

        actual_model = request.model

        if isinstance(
            response_payload,
            dict,
        ):

            actual_model = (
                response_payload.get(
                    "model"
                )
                or request.model
            )

        semantic_cache_stored = (
            await safe_semantic_store(
                tenant=tenant,
                feature=request.metadata.feature,
                requested_model=request.model,
                tier=tier.value,
                cache_text=cache_text,
                response=response_payload,
                actual_provider="router",
                actual_model=actual_model,
                temperature=request.temperature,
                max_tokens=request.max_tokens,
            )
        )

        # ====================================================
        # 9. REQUEST COMPLETED
        # ====================================================

        log_event(
            "request_completed",
            request_id=(
                request.metadata.request_id
            ),
            tenant=tenant,
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
            tier=tier.value,
            cache_status="miss",
            semantic_cache_stored=(
                semantic_cache_stored
            ),
        )

        # ====================================================
        # 10. RETURN RESPONSE
        # ====================================================

        return response_payload

    # ========================================================
    # ALL PROVIDERS FAILED
    # ========================================================

    except Exception as exc:

        error_type = (
            type(exc).__name__
        )

        error_message = str(exc)

        log_event(
            "request_failed",
            level="ERROR",
            request_id=(
                request.metadata.request_id
            ),
            tenant=tenant,
            feature=(
                request.metadata.feature
            ),
            requested_model=request.model,
            tier=tier.value,
            error_type=error_type,
            error_message=error_message,
        )

        raise HTTPException(
            status_code=502,
            detail={
                "error": "All LLM providers failed",
                "request_id": request.metadata.request_id,
            },
        ) from exc