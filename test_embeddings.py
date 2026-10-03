import asyncio
import math

from app.cache.embeddings import embed_text


def cosine_similarity(
    vector_a: list[float],
    vector_b: list[float],
) -> float:
    """
    Calculate cosine similarity:

        dot(A, B)
        -------------
        ||A|| * ||B||
    """

    dot_product = sum(
        a * b
        for a, b in zip(
            vector_a,
            vector_b,
        )
    )

    magnitude_a = math.sqrt(
        sum(
            a * a
            for a in vector_a
        )
    )

    magnitude_b = math.sqrt(
        sum(
            b * b
            for b in vector_b
        )
    )

    if magnitude_a == 0 or magnitude_b == 0:
        raise ValueError(
            "Cannot calculate similarity "
            "for a zero vector."
        )

    return (
        dot_product
        / (magnitude_a * magnitude_b)
    )


async def main():

    print(
        "\n========================================="
    )

    print(
        "COHERE EMBEDDING TEST"
    )

    print(
        "=========================================\n"
    )

    # --------------------------------------------------------
    # Stored cache document
    # --------------------------------------------------------

    document = (
        "A load balancer distributes incoming "
        "network traffic across multiple servers."
    )

    # --------------------------------------------------------
    # Semantically similar query
    # --------------------------------------------------------

    similar_query = (
        "What does a load balancer do?"
    )

    # --------------------------------------------------------
    # Unrelated query
    # --------------------------------------------------------

    unrelated_query = (
        "What is machine learning?"
    )

    # --------------------------------------------------------
    # Embed the stored document
    # --------------------------------------------------------

    print(
        "[TEST] Creating document embedding..."
    )

    document_vector = await embed_text(
        text=document,
        input_type="search_document",
    )

    print(
        "[TEST] Document vector dimension:",
        len(document_vector),
    )

    # --------------------------------------------------------
    # Embed both queries separately
    # --------------------------------------------------------

    print(
        "[TEST] Creating similar-query embedding..."
    )

    similar_vector = await embed_text(
        text=similar_query,
        input_type="search_query",
    )

    print(
        "[TEST] Creating unrelated-query embedding..."
    )

    unrelated_vector = await embed_text(
        text=unrelated_query,
        input_type="search_query",
    )

    # --------------------------------------------------------
    # Similarity
    # --------------------------------------------------------

    similar_score = cosine_similarity(
        similar_vector,
        document_vector,
    )

    unrelated_score = cosine_similarity(
        unrelated_vector,
        document_vector,
    )

    print(
        "\n[TEST] Similar query score:",
        round(similar_score, 4),
    )

    print(
        "[TEST] Unrelated query score:",
        round(unrelated_score, 4),
    )

    # --------------------------------------------------------
    # Basic sanity check
    # --------------------------------------------------------

    if similar_score <= unrelated_score:
        raise RuntimeError(
            "Semantic similarity test failed: "
            "the related query did not score "
            "higher than the unrelated query."
        )

    print(
        "\n[TEST] Similar query ranked higher: SUCCESS"
    )

    print(
        "\n========================================="
    )

    print(
        "COHERE EMBEDDING TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )


if __name__ == "__main__":
    asyncio.run(main())