import asyncio

from app.cache.embeddings import embed_text

from app.cache.semantic_cache import (
    build_cache_key,
    build_cache_text,
    build_scope_hash,
    semantic_cache,
)

from app.infra.redis_client import (
    redis_client,
)


async def main():

    print(
        "\n========================================="
    )

    print(
        "REDIS SEMANTIC CACHE TEST"
    )

    print(
        "=========================================\n"
    )

    # ========================================================
    # TEST CONFIGURATION
    # ========================================================

    tenant = "semantic-test-tenant"

    feature = "semantic-cache-test"

    requested_model = "auto"

    tier = "small"

    temperature = None

    max_tokens = None

    # ========================================================
    # ORIGINAL DOCUMENT / REQUEST
    # ========================================================

    original_messages = [
        {
            "role": "user",
            "content": (
                "What is a load balancer?"
            ),
        }
    ]

    # ========================================================
    # SEMANTICALLY SIMILAR REQUEST
    # ========================================================

    similar_messages = [
        {
            "role": "user",
            "content": (
                "Can you explain what "
                "a load balancer does?"
            ),
        }
    ]

    # ========================================================
    # UNRELATED REQUEST
    # ========================================================

    unrelated_messages = [
        {
            "role": "user",
            "content": (
                "What is machine learning?"
            ),
        }
    ]

    # ========================================================
    # BUILD CACHE TEXT
    # ========================================================

    original_text = build_cache_text(
        original_messages
    )

    similar_text = build_cache_text(
        similar_messages
    )

    unrelated_text = build_cache_text(
        unrelated_messages
    )

    print(
        "[TEST] Original text:",
        original_text,
    )

    print(
        "[TEST] Similar text:",
        similar_text,
    )

    print(
        "[TEST] Unrelated text:",
        unrelated_text,
    )

    # ========================================================
    # BUILD SCOPE
    # ========================================================

    scope_hash = build_scope_hash(
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
        tier=tier,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    # ========================================================
    # BUILD EXACT REDIS KEY
    # ========================================================

    original_key = build_cache_key(
        cache_text=original_text,
        scope_hash=scope_hash,
    )

    # ========================================================
    # CLEAN PREVIOUS TEST ENTRY
    # ========================================================

    await redis_client.delete(
        original_key
    )

    # ========================================================
    # CREATE REDIS SEARCH INDEX
    # ========================================================

    print(
        "\n[TEST] Ensuring semantic cache index..."
    )

    await semantic_cache.ensure_index()

    # ========================================================
    # CREATE STORED DOCUMENT EMBEDDING
    # ========================================================

    print(
        "\n[TEST] Creating stored-document embedding..."
    )

    document_vector = await embed_text(
        text=original_text,
        input_type="search_document",
    )

    print(
        "[TEST] Document vector dimension:",
        len(document_vector),
    )

    if len(document_vector) != 1024:

        raise RuntimeError(
            "Expected a 1024-dimensional "
            "document embedding."
        )

    # ========================================================
    # FAKE LLM RESPONSE
    # ========================================================

    fake_response = {
        "id": "semantic-cache-test-001",
        "object": "chat.completion",
        "model": "test-model",
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": (
                        "A load balancer distributes "
                        "incoming traffic across "
                        "multiple servers."
                    ),
                },
                "finish_reason": "stop",
            }
        ],
    }

    # ========================================================
    # STORE DOCUMENT IN SEMANTIC CACHE
    # ========================================================

    print(
        "\n[TEST] Storing original response..."
    )

    await semantic_cache.set(
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
        tier=tier,
        temperature=temperature,
        max_tokens=max_tokens,
        cache_text=original_text,
        document_vector=document_vector,
        response=fake_response,
        actual_provider="test-provider",
        actual_model="test-model",
    )

    # ========================================================
    # SIMILAR QUERY EMBEDDING
    # ========================================================

    print(
        "\n[TEST] Creating similar-query embedding..."
    )

    similar_vector = await embed_text(
        text=similar_text,
        input_type="search_query",
    )

    # ========================================================
    # SEMANTIC SEARCH - EXPECT HIT
    # ========================================================

    similar_result = await semantic_cache.search(
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
        tier=tier,
        temperature=temperature,
        max_tokens=max_tokens,
        query_vector=similar_vector,
    )

    if similar_result is None:

        raise RuntimeError(
            "Expected a semantic HIT for "
            "the similar query."
        )

    print(
        "[TEST] Similar query: HIT"
    )

    print(
        "[TEST] Similarity:",
        round(
            similar_result["similarity"],
            4,
        ),
    )

    print(
        "[TEST] Distance:",
        round(
            similar_result["distance"],
            4,
        ),
    )

    print(
        "[TEST] Provider:",
        similar_result["actual_provider"],
    )

    print(
        "[TEST] Model:",
        similar_result["actual_model"],
    )

    # ========================================================
    # VERIFY RESPONSE
    # ========================================================

    if (
        similar_result["response"]
        != fake_response
    ):

        raise RuntimeError(
            "Semantic cache returned an "
            "unexpected response."
        )

    print(
        "[TEST] Cached response: CORRECT"
    )

    # ========================================================
    # UNRELATED QUERY
    # ========================================================

    print(
        "\n[TEST] Creating unrelated-query embedding..."
    )

    unrelated_vector = await embed_text(
        text=unrelated_text,
        input_type="search_query",
    )

    # ========================================================
    # SEMANTIC SEARCH - EXPECT MISS
    # ========================================================

    unrelated_result = await semantic_cache.search(
        tenant=tenant,
        feature=feature,
        requested_model=requested_model,
        tier=tier,
        temperature=temperature,
        max_tokens=max_tokens,
        query_vector=unrelated_vector,
    )

    if unrelated_result is not None:

        raise RuntimeError(
            "Expected semantic MISS for "
            "the unrelated query."
        )

    print(
        "[TEST] Unrelated query: MISS"
    )

    # ========================================================
    # TENANT ISOLATION
    # ========================================================

    other_tenant_result = (
        await semantic_cache.search(
            tenant="another-tenant",
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            temperature=temperature,
            max_tokens=max_tokens,
            query_vector=similar_vector,
        )
    )

    if other_tenant_result is not None:

        raise RuntimeError(
            "Tenant isolation failed: "
            "another tenant accessed "
            "the cached response."
        )

    print(
        "[TEST] Tenant isolation: SUCCESS"
    )

    # ========================================================
    # GENERATION SCOPE ISOLATION
    # ========================================================

    different_tier_result = (
        await semantic_cache.search(
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier="medium",
            temperature=temperature,
            max_tokens=max_tokens,
            query_vector=similar_vector,
        )
    )

    if different_tier_result is not None:

        raise RuntimeError(
            "Generation scope isolation failed: "
            "a different tier accessed "
            "the cached response."
        )

    print(
        "[TEST] Tier isolation: SUCCESS"
    )

    # ========================================================
    # CLEANUP
    # ========================================================

    await redis_client.delete(
        original_key
    )

    await redis_client.aclose()

    print(
        "\n========================================="
    )

    print(
        "REDIS SEMANTIC CACHE TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )


if __name__ == "__main__":
    asyncio.run(main())