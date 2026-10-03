import hashlib
import json
import os
import struct
import time
from typing import Any

from dotenv import load_dotenv
from redis.commands.search.field import (
    NumericField,
    TagField,
    TextField,
    VectorField,
)
from redis.commands.search.query import Query

# Redis-py changed this module name across versions.
# Newer versions use index_definition.
# Older versions use indexDefinition.
try:
    from redis.commands.search.index_definition import (
        IndexDefinition,
        IndexType,
    )
except ModuleNotFoundError:
    from redis.commands.search.indexDefinition import (
        IndexDefinition,
        IndexType,
    )

from app.gateway.request_logger import log_event
from app.infra.redis_client import redis_client


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

INDEX_NAME = "gateway:semantic_cache:index"

KEY_PREFIX = "gateway:semantic_cache:v1:"

VECTOR_FIELD = "embedding"

EMBEDDING_DIMENSION = 1024

CACHE_TTL_SECONDS = int(
    os.getenv(
        "CACHE_TTL_SECONDS",
        "300",
    )
)

MAX_DISTANCE = float(
    os.getenv(
        "SEMANTIC_CACHE_MAX_DISTANCE",
        "0.45",
    )
)


# ============================================================
# VECTOR SERIALIZATION
# ============================================================

def vector_to_bytes(
    vector: list[float],
) -> bytes:
    """
    Convert a 1024-dimensional float vector into FLOAT32
    binary representation for Redis vector search.
    """

    if len(vector) != EMBEDDING_DIMENSION:
        raise ValueError(
            "Invalid vector dimension: "
            f"{len(vector)}. "
            f"Expected {EMBEDDING_DIMENSION}."
        )

    return struct.pack(
        f"<{EMBEDDING_DIMENSION}f",
        *vector,
    )


# ============================================================
# BUILD CACHE TEXT
# ============================================================

def build_cache_text(
    messages: list[dict[str, str]],
) -> str:
    """
    Build the semantic-cache text representation.
    """

    return "\n".join(
        f"{message.get('role', '')}: "
        f"{message.get('content', '')}"
        for message in messages
    )


# ============================================================
# HASH VALUE
# ============================================================

def hash_value(
    value: str,
) -> str:
    """
    Return a deterministic SHA-256 hash.
    """

    return hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()


# ============================================================
# BUILD SCOPE HASH
# ============================================================

def build_scope_hash(
    tenant: str,
    feature: str,
    requested_model: str,
    tier: str,
    temperature: float | None,
    max_tokens: int | None,
) -> str:
    """
    Build a deterministic hash for semantic-cache scope.

    This ensures semantic matches stay inside the same
    tenant / feature / model / tier / generation configuration.
    """

    payload = {
        "tenant": tenant,
        "feature": feature,
        "requested_model": requested_model,
        "tier": tier,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(
            ",",
            ":",
        ),
        ensure_ascii=False,
    )

    return hash_value(
        canonical_payload
    )


# ============================================================
# BUILD CACHE KEY
# ============================================================

def build_cache_key(
    cache_text: str,
    scope_hash: str,
) -> str:
    """
    Build a deterministic Redis document key.

    Raw prompt text is never placed directly into the key.
    """

    text_hash = hash_value(
        cache_text
    )

    return (
        f"{KEY_PREFIX}"
        f"{text_hash[:16]}:"
        f"{scope_hash}"
    )


# ============================================================
# DOCUMENT FIELD HELPER
# ============================================================

def get_document_field(
    document: Any,
    field_name: str,
) -> Any:
    """
    Read a Redis document field in a way that works with
    Document-like objects and dictionary-like objects.
    """

    value = getattr(
        document,
        field_name,
        None,
    )

    if value is not None:
        return value

    if isinstance(
        document,
        dict,
    ):
        return document.get(
            field_name
        )

    return None


# ============================================================
# REDIS SEMANTIC CACHE
# ============================================================

class RedisSemanticCache:

    # ========================================================
    # ENSURE INDEX
    # ========================================================

    async def ensure_index(self) -> None:
        """
        Ensure that the Redis HNSW semantic-cache index exists.
        """

        # ----------------------------------------------------
        # Check whether index already exists
        # ----------------------------------------------------

        try:

            await redis_client.ft(
                INDEX_NAME
            ).info()

            log_event(
                "semantic_cache_index_ready",
                index=INDEX_NAME,
            )

            return

        except Exception:
            pass

        # ----------------------------------------------------
        # Create index
        # ----------------------------------------------------

        schema = (
            TagField(
                "tenant_hash"
            ),
            TagField(
                "feature_hash"
            ),
            TagField(
                "scope_hash"
            ),
            TagField(
                "tier"
            ),
            TagField(
                "requested_model_hash"
            ),
            TextField(
                "response"
            ),
            TextField(
                "actual_provider"
            ),
            TextField(
                "actual_model"
            ),
            NumericField(
                "created_at"
            ),
            VectorField(
                VECTOR_FIELD,
                "HNSW",
                {
                    "TYPE": "FLOAT32",
                    "DIM": EMBEDDING_DIMENSION,
                    "DISTANCE_METRIC": "COSINE",
                    "M": 16,
                    "EF_CONSTRUCTION": 200,
                },
            ),
        )

        definition = IndexDefinition(
            prefix=[
                KEY_PREFIX
            ],
            index_type=IndexType.HASH,
        )

        try:

            await redis_client.ft(
                INDEX_NAME
            ).create_index(
                schema,
                definition=definition,
            )

            log_event(
                "semantic_cache_index_created",
                index=INDEX_NAME,
                algorithm="HNSW",
                dimension=EMBEDDING_DIMENSION,
                distance_metric="COSINE",
            )

        except Exception as error:

            error_message = str(
                error
            ).lower()

            # Another process may have created it
            # between INFO and CREATE.
            if (
                "already exists"
                in error_message
            ):
                log_event(
                    "semantic_cache_index_ready",
                    index=INDEX_NAME,
                )
                return

            log_event(
                "semantic_cache_index_creation_failed",
                level="ERROR",
                index=INDEX_NAME,
                error_type=type(error).__name__,
                error_message=str(error),
            )

            raise

    # ========================================================
    # SEARCH
    # ========================================================

    async def search(
        self,
        tenant: str,
        feature: str,
        requested_model: str,
        tier: str,
        query_vector: list[float],
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Search for the nearest semantic-cache entry within
        the correct request scope.
        """

        await self.ensure_index()

        # ----------------------------------------------------
        # Validate vector
        # ----------------------------------------------------

        if (
            len(query_vector)
            != EMBEDDING_DIMENSION
        ):
            raise ValueError(
                "Invalid query vector dimension: "
                f"{len(query_vector)}. "
                f"Expected {EMBEDDING_DIMENSION}."
            )

        # ----------------------------------------------------
        # Hash scope fields
        # ----------------------------------------------------

        tenant_hash = hash_value(
            tenant
        )

        feature_hash = hash_value(
            feature
        )

        requested_model_hash = hash_value(
            requested_model
        )

        scope_hash = build_scope_hash(
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # ----------------------------------------------------
        # Build strict metadata filter
        # ----------------------------------------------------

        filter_query = (
            f"@tenant_hash:{{{tenant_hash}}} "
            f"@feature_hash:{{{feature_hash}}} "
            f"@scope_hash:{{{scope_hash}}} "
            f"@tier:{{{tier}}} "
            f"@requested_model_hash:"
            f"{{{requested_model_hash}}}"
        )

        # ----------------------------------------------------
        # KNN query
        # ----------------------------------------------------

        query = Query(
            f"({filter_query})=>"
            f"[KNN 1 "
            f"@{VECTOR_FIELD} "
            f"$query_vector "
            f"AS vector_distance]"
        )

        query = (
            query
            .sort_by(
                "vector_distance",
                asc=True,
            )
            .return_fields(
                "response",
                "actual_provider",
                "actual_model",
                "created_at",
                "vector_distance",
            )
            .paging(
                0,
                1,
            )
            .dialect(2)
        )

        # ----------------------------------------------------
        # Search started
        # ----------------------------------------------------

        log_event(
            "semantic_cache_search_started",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
        )

        try:

            result = await redis_client.ft(
                INDEX_NAME
            ).search(
                query,
                query_params={
                    "query_vector": vector_to_bytes(
                        query_vector
                    )
                },
            )

        except Exception as error:

            log_event(
                "semantic_cache_search_failed",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
                error_type=type(error).__name__,
                error_message=str(error),
            )

            raise

        # ----------------------------------------------------
        # No candidate
        # ----------------------------------------------------

        if not result.docs:

            log_event(
                "semantic_cache_no_candidate",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
            )

            return None

        document = result.docs[0]

        # ----------------------------------------------------
        # Read distance
        # ----------------------------------------------------

        raw_distance = get_document_field(
            document,
            "vector_distance",
        )

        if raw_distance is None:

            log_event(
                "semantic_cache_missing_distance",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
            )

            return None

        distance = float(
            raw_distance
        )

        similarity = (
            1.0 - distance
        )

        # ----------------------------------------------------
        # Candidate found
        # ----------------------------------------------------

        log_event(
            "semantic_cache_candidate_found",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            distance=distance,
            similarity=similarity,
            threshold=MAX_DISTANCE,
        )

        # ----------------------------------------------------
        # Similarity threshold check
        # ----------------------------------------------------

        if distance > MAX_DISTANCE:

            log_event(
                "semantic_cache_similarity_miss",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
                distance=distance,
                similarity=similarity,
                threshold=MAX_DISTANCE,
            )

            return None

        # ----------------------------------------------------
        # Extract cached fields
        # ----------------------------------------------------

        raw_response = get_document_field(
            document,
            "response",
        )

        actual_provider = get_document_field(
            document,
            "actual_provider",
        )

        actual_model = get_document_field(
            document,
            "actual_model",
        )

        created_at = get_document_field(
            document,
            "created_at",
        )

        # ----------------------------------------------------
        # Parse cached response
        # ----------------------------------------------------

        if isinstance(
            raw_response,
            str,
        ):

            try:

                parsed_response = json.loads(
                    raw_response
                )

            except json.JSONDecodeError:

                log_event(
                    "semantic_cache_invalid_response",
                    level="WARNING",
                    tenant=tenant,
                    feature=feature,
                    requested_model=requested_model,
                    tier=tier,
                )

                return None

        else:

            parsed_response = raw_response

        # ----------------------------------------------------
        # Build return payload
        # ----------------------------------------------------

        result_payload = {
            "response": parsed_response,
            "actual_provider": actual_provider,
            "actual_model": actual_model,
            "created_at": created_at,
            "distance": distance,
            "similarity": similarity,
        }

        # ----------------------------------------------------
        # Semantic HIT
        # ----------------------------------------------------

        log_event(
            "semantic_cache_hit",
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            distance=distance,
            similarity=similarity,
            threshold=MAX_DISTANCE,
            actual_provider=actual_provider,
            actual_model=actual_model,
        )

        return result_payload

    # ========================================================
    # SET
    # ========================================================

    async def set(
        self,
        tenant: str,
        feature: str,
        requested_model: str,
        tier: str,
        cache_text: str,
        document_vector: list[float],
        response: Any,
        actual_provider: str,
        actual_model: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """
        Store a successful response in the semantic cache.
        """

        await self.ensure_index()

        # ----------------------------------------------------
        # Validate vector
        # ----------------------------------------------------

        if (
            len(document_vector)
            != EMBEDDING_DIMENSION
        ):
            raise ValueError(
                "Invalid document vector dimension: "
                f"{len(document_vector)}. "
                f"Expected {EMBEDDING_DIMENSION}."
            )

        # ----------------------------------------------------
        # Scope hashes
        # ----------------------------------------------------

        tenant_hash = hash_value(
            tenant
        )

        feature_hash = hash_value(
            feature
        )

        requested_model_hash = hash_value(
            requested_model
        )

        scope_hash = build_scope_hash(
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # ----------------------------------------------------
        # Cache key
        # ----------------------------------------------------

        key = build_cache_key(
            cache_text=cache_text,
            scope_hash=scope_hash,
        )

        # ----------------------------------------------------
        # Serialize response
        # ----------------------------------------------------

        serialized_response = json.dumps(
            response,
            ensure_ascii=False,
            default=str,
        )

        # ----------------------------------------------------
        # Create timestamp
        # ----------------------------------------------------

        created_at = time.time()

        # ----------------------------------------------------
        # Redis HASH document
        # ----------------------------------------------------

        document = {
            "tenant_hash": tenant_hash,
            "feature_hash": feature_hash,
            "scope_hash": scope_hash,
            "tier": tier,
            "requested_model_hash": (
                requested_model_hash
            ),
            "response": serialized_response,
            "actual_provider": actual_provider,
            "actual_model": actual_model,
            "created_at": created_at,
            VECTOR_FIELD: vector_to_bytes(
                document_vector
            ),
        }

        # ----------------------------------------------------
        # Store started
        # ----------------------------------------------------

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

            await redis_client.hset(
                key,
                mapping=document,
            )

            await redis_client.expire(
                key,
                CACHE_TTL_SECONDS,
            )

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

            raise

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
            ttl_seconds=CACHE_TTL_SECONDS,
        )

    # ========================================================
    # DELETE
    # ========================================================

    async def delete(
        self,
        tenant: str,
        feature: str,
        requested_model: str,
        tier: str,
        cache_text: str,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None:
        """
        Delete a semantic-cache entry.
        """

        scope_hash = build_scope_hash(
            tenant=tenant,
            feature=feature,
            requested_model=requested_model,
            tier=tier,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        key = build_cache_key(
            cache_text=cache_text,
            scope_hash=scope_hash,
        )

        try:

            deleted = await redis_client.delete(
                key
            )

            log_event(
                "semantic_cache_deleted",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
                deleted=bool(deleted),
            )

        except Exception as error:

            log_event(
                "semantic_cache_delete_failed",
                level="WARNING",
                tenant=tenant,
                feature=feature,
                requested_model=requested_model,
                tier=tier,
                error_type=type(error).__name__,
                error_message=str(error),
            )

            raise


# ============================================================
# GLOBAL SEMANTIC CACHE
# ============================================================

semantic_cache = RedisSemanticCache()