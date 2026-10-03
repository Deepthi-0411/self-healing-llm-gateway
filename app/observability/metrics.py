from prometheus_client import Counter, Gauge, Histogram


# ============================================================
# HTTP REQUEST METRICS
# ============================================================

gateway_http_requests_total = Counter(
    "gateway_http_requests_total",
    "Total HTTP requests received by the gateway.",
    ["method", "path", "status"],
)


gateway_request_latency_seconds = Histogram(
    "gateway_request_latency_seconds",
    "Gateway HTTP request latency in seconds.",
    ["path"],
    buckets=(
        0.005,
        0.01,
        0.025,
        0.05,
        0.1,
        0.25,
        0.5,
        1.0,
        2.5,
        5.0,
        10.0,
        30.0,
        60.0,
    ),
)


# ============================================================
# GATEWAY OUTCOME METRICS
# ============================================================

gateway_requests_total = Counter(
    "gateway_requests_total",
    "Total gateway request outcomes.",
    ["outcome"],
)


# ============================================================
# PROVIDER METRICS
# ============================================================

gateway_provider_requests_total = Counter(
    "gateway_provider_requests_total",
    "Total provider request attempts completed.",
    ["provider", "outcome"],
)


gateway_provider_failures_total = Counter(
    "gateway_provider_failures_total",
    "Total provider failures.",
    ["provider", "error_category"],
)


gateway_provider_fallbacks_total = Counter(
    "gateway_provider_fallbacks_total",
    "Total provider fallback events.",
)

gateway_provider_latency_seconds = Histogram(
    "gateway_provider_latency_seconds",
    "Provider request latency in seconds.",
    ["provider"],
)

gateway_provider_health = Gauge(
    "gateway_provider_health",
    "Current known provider availability. 1 means available, 0 means unavailable.",
    ["provider"],
)


# ============================================================
# CACHE METRICS
# ============================================================

gateway_cache_hits_total = Counter(
    "gateway_cache_hits_total",
    "Total cache hits.",
    ["cache_type"],
)


gateway_cache_misses_total = Counter(
    "gateway_cache_misses_total",
    "Total cache misses.",
    ["cache_type"],
)


gateway_cache_errors_total = Counter(
    "gateway_cache_errors_total",
    "Total cache errors.",
    ["cache_type", "operation"],
)


# ============================================================
# ADMISSION CONTROL METRICS
# ============================================================

gateway_rate_limit_rejections_total = Counter(
    "gateway_rate_limit_rejections_total",
    "Total requests rejected by the tenant rate limiter.",
)


gateway_budget_rejections_total = Counter(
    "gateway_budget_rejections_total",
    "Total requests rejected by the tenant budget.",
)


# ============================================================
# RETRY METRICS
# ============================================================

gateway_retry_attempts_total = Counter(
    "gateway_retry_attempts_total",
    "Total failed retry attempts.",
)


# ============================================================
# REDIS HEALTH
# ============================================================

gateway_redis_up = Gauge(
    "gateway_redis_up",
    "Redis health status. 1 means healthy and 0 means unavailable.",
)


# ============================================================
# STRUCTURED LOG EVENT -> PROMETHEUS METRIC
# ============================================================

def record_event_metrics(
    event: str,
    fields: dict,
) -> None:
    """
    Convert existing structured gateway events into
    Prometheus metrics.

    Metrics must never break the gateway request path.
    """

    try:

        # ----------------------------------------------------
        # REQUEST OUTCOMES
        # ----------------------------------------------------

        if event == "request_completed":

            gateway_requests_total.labels(
                outcome="success"
            ).inc()

        elif event == "request_completed_from_exact_cache":

            gateway_requests_total.labels(
                outcome="exact_cache_hit"
            ).inc()

        elif event == "request_completed_from_semantic_cache":

            gateway_requests_total.labels(
                outcome="semantic_cache_hit"
            ).inc()

        elif event == "request_rejected_rate_limit":

            gateway_requests_total.labels(
                outcome="rate_limited"
            ).inc()

            gateway_rate_limit_rejections_total.inc()

        elif event == "request_rejected_budget":

            gateway_requests_total.labels(
                outcome="budget_rejected"
            ).inc()

            gateway_budget_rejections_total.inc()

        elif event == "request_failed":

            gateway_requests_total.labels(
                outcome="provider_error"
            ).inc()

        # ----------------------------------------------------
        # EXACT CACHE
        # ----------------------------------------------------

        elif event == "exact_cache_hit":

            gateway_cache_hits_total.labels(
                cache_type="exact"
            ).inc()

        elif event == "exact_cache_miss":

            gateway_cache_misses_total.labels(
                cache_type="exact"
            ).inc()

        elif event == "exact_cache_store_failed_safely":

            gateway_cache_errors_total.labels(
                cache_type="exact",
                operation="store",
            ).inc()

        # ----------------------------------------------------
        # SEMANTIC CACHE
        # ----------------------------------------------------

        elif event == "semantic_cache_hit":

            gateway_cache_hits_total.labels(
                cache_type="semantic"
            ).inc()

        elif event == "semantic_cache_miss":

            gateway_cache_misses_total.labels(
                cache_type="semantic"
            ).inc()

        elif event == "semantic_cache_lookup_failed":

            gateway_cache_errors_total.labels(
                cache_type="semantic",
                operation="lookup",
            ).inc()

        elif event == "semantic_cache_lookup_fail_open":

            gateway_cache_errors_total.labels(
                cache_type="semantic",
                operation="lookup",
            ).inc()

        elif event == "semantic_cache_store_failed":

            gateway_cache_errors_total.labels(
                cache_type="semantic",
                operation="store",
            ).inc()

        elif event == "semantic_cache_store_fail_open":

            gateway_cache_errors_total.labels(
                cache_type="semantic",
                operation="store",
            ).inc()

        # ----------------------------------------------------
        # PROVIDER REQUESTS
        # ----------------------------------------------------

        elif event == "provider_request_succeeded":

            provider = str(
                fields.get(
                    "provider",
                    "unknown",
                )
            )

            gateway_provider_requests_total.labels(
                provider=provider,
                outcome="success",
            ).inc()

        elif event == "provider_request_failed":

            provider = str(
                fields.get(
                    "provider",
                    "unknown",
                )
            )

            error_category = str(
                fields.get(
                    "error_category",
                    "unknown",
                )
            )

            gateway_provider_requests_total.labels(
                provider=provider,
                outcome="failure",
            ).inc()

            gateway_provider_failures_total.labels(
                provider=provider,
                error_category=error_category,
            ).inc()

        # ----------------------------------------------------
        # PROVIDER FALLBACK
        # ----------------------------------------------------

        elif event == "provider_fallback_started":

            gateway_provider_fallbacks_total.inc()

        # ----------------------------------------------------
        # RETRIES
        # ----------------------------------------------------

        elif event == "retry_attempt_failed":

            gateway_retry_attempts_total.inc()

        # ----------------------------------------------------
        # REDIS
        # ----------------------------------------------------

        elif event == "redis_health_check":

            gateway_redis_up.set(
                1
                if fields.get("redis_status") == "connected"
                else 0
            )

        elif event == "redis_health_check_failed":

            gateway_redis_up.set(0)

    except Exception:
        # Observability must never become a request failure.
        return