from app.llm.tiering import ModelTier


# ============================================================
# PRIMARY MODELS
# Gemini is the main provider.
# ============================================================

MODEL_BY_TIER = {
    ModelTier.SMALL: {
        "provider": "gemini",
        "model": "gemini/gemini-3.6-flash",
    },

    ModelTier.MEDIUM: {
        "provider": "gemini",
        "model": "gemini/gemini-3.6-flash",
    },

    ModelTier.LARGE: {
        "provider": "gemini",
        "model": "gemini/gemini-3.1-pro-preview",
    },
}


# ============================================================
# FIRST FALLBACK
# Cloudflare Workers AI
# ============================================================

FALLBACK_MODEL_BY_TIER = {
    ModelTier.SMALL: {
        "provider": "cloudflare",
        "model": (
            "cloudflare/"
            "@cf/meta/llama-3.1-8b-instruct-fp8"
        ),
    },

    ModelTier.MEDIUM: {
        "provider": "cloudflare",
        "model": (
            "cloudflare/"
            "@cf/meta/llama-3.1-8b-instruct-fp8"
        ),
    },

    ModelTier.LARGE: {
        "provider": "cohere",
        "model": "cohere/command-a-plus-05-2026",
    },
}


# ============================================================
# SECOND FALLBACK
# Cohere / Cloudflare
# ============================================================

SECONDARY_FALLBACK_MODEL_BY_TIER = {
    ModelTier.SMALL: {
        "provider": "cohere",
        "model": "cohere/command-a-plus-05-2026",
    },

    ModelTier.MEDIUM: {
        "provider": "cohere",
        "model": "cohere/command-a-plus-05-2026",
    },

    ModelTier.LARGE: {
        "provider": "cloudflare",
        "model": (
            "cloudflare/"
            "@cf/meta/llama-3.1-8b-instruct-fp8"
        ),
    },
}


def get_model_for_tier(
    tier: ModelTier,
) -> dict[str, str]:
    """
    Return the primary model for a tier.
    """
    if tier not in MODEL_BY_TIER:
        raise ValueError(
            f"No primary model configured for tier: {tier}"
        )

    return MODEL_BY_TIER[tier]


def get_fallback_model_for_tier(
    tier: ModelTier,
) -> dict[str, str]:
    """
    Return the first fallback model for a tier.
    """
    if tier not in FALLBACK_MODEL_BY_TIER:
        raise ValueError(
            f"No fallback model configured for tier: {tier}"
        )

    return FALLBACK_MODEL_BY_TIER[tier]


def get_secondary_fallback_model_for_tier(
    tier: ModelTier,
) -> dict[str, str]:
    """
    Return the second fallback model for a tier.
    """
    if tier not in SECONDARY_FALLBACK_MODEL_BY_TIER:
        raise ValueError(
            "No secondary fallback model configured "
            f"for tier: {tier}"
        )

    return SECONDARY_FALLBACK_MODEL_BY_TIER[tier]


def get_provider_chain_for_tier(
    tier: ModelTier,
) -> list[dict[str, str]]:
    """
    Return the complete provider/model execution chain.

    Example:

        Gemini
          ↓ failure
        Cloudflare
          ↓ failure
        Cohere
    """

    return [
        get_model_for_tier(tier),
        get_fallback_model_for_tier(tier),
        get_secondary_fallback_model_for_tier(tier),
    ]