import asyncio
import os

import cohere
from dotenv import load_dotenv

from app.gateway.request_logger import log_event


load_dotenv()


# ============================================================
# CONFIGURATION
# ============================================================

COHERE_EMBED_MODEL = "embed-v4.0"

EMBEDDING_DIMENSION = 1024


# ============================================================
# COHERE CLIENT
# ============================================================

def get_cohere_client() -> cohere.ClientV2:
    """
    Create a Cohere client using the configured API key.
    """

    api_key = os.getenv(
        "COHERE_API_KEY"
    )

    if not api_key:

        raise RuntimeError(
            "COHERE_API_KEY is not configured."
        )

    return cohere.ClientV2(
        api_key=api_key
    )


# ============================================================
# TEXT EMBEDDING
# ============================================================

async def embed_text(
    text: str,
    input_type: str,
) -> list[float]:
    """
    Generate a Cohere embedding.

    Supported input types:

        search_query
        search_document

    Returns:
        A validated 1024-dimensional float vector.

    The text itself is intentionally never logged.
    """

    # --------------------------------------------------------
    # Validate input type
    # --------------------------------------------------------

    if input_type not in {
        "search_query",
        "search_document",
    }:

        raise ValueError(
            "input_type must be either "
            "'search_query' or "
            "'search_document'."
        )

    # --------------------------------------------------------
    # Embedding request started
    # --------------------------------------------------------

    log_event(
        "embedding_request_started",
        provider="cohere",
        model=COHERE_EMBED_MODEL,
        input_type=input_type,
        expected_dimension=EMBEDDING_DIMENSION,
    )

    try:

        client = get_cohere_client()

        # ----------------------------------------------------
        # Cohere SDK call
        #
        # The SDK call is synchronous, so run it in a worker
        # thread to avoid blocking the async event loop.
        # ----------------------------------------------------

        def make_request():

            return client.embed(
                texts=[text],
                model=COHERE_EMBED_MODEL,
                input_type=input_type,
                output_dimension=EMBEDDING_DIMENSION,
                embedding_types=["float"],
            )

        response = await asyncio.to_thread(
            make_request
        )

        # ----------------------------------------------------
        # Extract embeddings
        # ----------------------------------------------------

        embeddings = response.embeddings.float

        if not embeddings:

            raise RuntimeError(
                "Cohere returned no embeddings."
            )

        vector = embeddings[0]

        # ----------------------------------------------------
        # Validate dimension
        # ----------------------------------------------------

        if len(vector) != EMBEDDING_DIMENSION:

            raise RuntimeError(
                "Unexpected embedding dimension: "
                f"{len(vector)}. "
                f"Expected {EMBEDDING_DIMENSION}."
            )

        # ----------------------------------------------------
        # Normalize values to Python floats
        # ----------------------------------------------------

        normalized_vector = [
            float(value)
            for value in vector
        ]

        # ----------------------------------------------------
        # Success log
        # ----------------------------------------------------

        log_event(
            "embedding_request_succeeded",
            provider="cohere",
            model=COHERE_EMBED_MODEL,
            input_type=input_type,
            dimension=len(normalized_vector),
        )

        return normalized_vector

    except Exception as error:

        # ----------------------------------------------------
        # Failure log
        #
        # The original text and API key are never included.
        # ----------------------------------------------------

        log_event(
            "embedding_request_failed",
            level="WARNING",
            provider="cohere",
            model=COHERE_EMBED_MODEL,
            input_type=input_type,
            error_type=type(error).__name__,
            error_message=str(error),
        )

        raise