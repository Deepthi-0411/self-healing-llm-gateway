from enum import Enum


class ModelTier(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"


# ============================================================
# HIGH-COMPLEXITY SIGNALS
# ============================================================

LARGE_KEYWORDS = {
    "architecture",
    "architect",
    "design",
    "debug",
    "optimize",
    "optimise",
    "analyze",
    "analyse",
    "reason",
    "reasoning",
    "derive",
    "prove",
    "investigate",
    "root cause",
    "distributed",
    "scalable",
    "fault tolerant",
    "fault-tolerant",
    "microservices",
    "system design",
    "tradeoff",
    "trade-off",
    "failure recovery",
}


# ============================================================
# TECHNICAL / MEDIUM-COMPLEXITY SIGNALS
# ============================================================

MEDIUM_KEYWORDS = {
    "api",
    "rest",
    "http",
    "https",
    "endpoint",
    "client",
    "server",
    "database",
    "sql",
    "redis",
    "docker",
    "fastapi",
    "python",
    "java",
    "machine learning",
    "deep learning",
    "genai",
    "llm",
    "model",
    "algorithm",
    "framework",
    "backend",
    "frontend",
    "authentication",
    "authorization",
    "json",
    "cache",
    "caching",
    "request",
    "response",
}


# ============================================================
# CODE SIGNALS
# ============================================================

CODE_MARKERS = {
    "```",
    "def ",
    "class ",
    "import ",
    "from ",
    "traceback",
    "exception",
    "stack trace",
    "syntaxerror",
    "typeerror",
    "attributeerror",
    "nullpointerexception",
    "segmentation fault",
}


def classify_request(
    messages: list[dict[str, str]]
) -> ModelTier:
    """
    Classify an incoming request into:

        SMALL
        MEDIUM
        LARGE

    The classification is based on:
        - message length
        - large-complexity keywords
        - technical keywords
        - code markers
        - conversation depth
    """

    # ========================================================
    # Extract user text
    # ========================================================

    text = " ".join(
        message.get("content", "")
        for message in messages
        if message.get("role") == "user"
    ).strip()

    text_lower = text.lower()

    word_count = len(text.split())

    # ========================================================
    # Count large-complexity signals
    # ========================================================

    large_matches = [
        keyword
        for keyword in LARGE_KEYWORDS
        if keyword in text_lower
    ]

    large_match_count = len(
        large_matches
    )

    # ========================================================
    # Count medium technical signals
    # ========================================================

    medium_matches = [
        keyword
        for keyword in MEDIUM_KEYWORDS
        if keyword in text_lower
    ]

    medium_match_count = len(
        medium_matches
    )

    # ========================================================
    # Code detection
    # ========================================================

    has_code_marker = any(
        marker in text_lower
        for marker in CODE_MARKERS
    )

    # ========================================================
    # LARGE CLASSIFICATION
    # ========================================================

    # Strong architecture / reasoning signals
    if large_match_count >= 2:
        print(
            "[Tiering] LARGE "
            f"(large signals: {large_matches})"
        )
        return ModelTier.LARGE

    # One very strong signal + enough context
    if large_match_count >= 1 and word_count >= 25:
        print(
            "[Tiering] LARGE "
            f"(large signal: {large_matches})"
        )
        return ModelTier.LARGE

    # Code-heavy requests are usually large
    if has_code_marker:
        print(
            "[Tiering] LARGE "
            "(code detected)"
        )
        return ModelTier.LARGE

    # Very long requests
    if word_count > 120:
        print(
            "[Tiering] LARGE "
            "(long request)"
        )
        return ModelTier.LARGE

    # ========================================================
    # MEDIUM CLASSIFICATION
    # ========================================================

    # Multiple technical signals
    if medium_match_count >= 2:
        print(
            "[Tiering] MEDIUM "
            f"(technical signals: {medium_matches})"
        )
        return ModelTier.MEDIUM

    # A single technical signal in a reasonably
    # detailed request
    if (
        medium_match_count == 1
        and word_count >= 10
    ):
        print(
            "[Tiering] MEDIUM "
            f"(technical signal: {medium_matches})"
        )
        return ModelTier.MEDIUM

    # Longer general questions
    if word_count > 40:
        print(
            "[Tiering] MEDIUM "
            "(moderately long request)"
        )
        return ModelTier.MEDIUM

    # Multiple-message conversation
    if len(messages) >= 6:
        print(
            "[Tiering] MEDIUM "
            "(conversation depth)"
        )
        return ModelTier.MEDIUM

    # ========================================================
    # SMALL
    # ========================================================

    print(
        "[Tiering] SMALL"
    )

    return ModelTier.SMALL