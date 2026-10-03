import os

from dotenv import load_dotenv
from litellm import acompletion


load_dotenv()


def get_required_env(name: str) -> str:
    """
    Read a required environment variable.

    Raises:
        RuntimeError: If the variable is missing or empty.
    """
    value = os.getenv(name)

    if not value:
        raise RuntimeError(
            f"Required environment variable is missing: {name}"
        )

    return value


async def call_model(
    model: str,
    messages: list[dict[str, str]],
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    """
    Common model caller used by all providers.

    Provider-specific credentials are injected based on the
    LiteLLM model prefix.
    """

    kwargs = {
        "model": model,
        "messages": messages,
    }

    if max_tokens is not None:
        kwargs["max_tokens"] = max_tokens

    # ---------------------------------------------------------
    # Gemini
    # ---------------------------------------------------------
    if model.startswith("gemini/"):
        kwargs["api_key"] = get_required_env("GEMINI_API_KEY")

        # Gemini 3.x currently warns about temperature/top_p/top_k.
        # We therefore do not send temperature to Gemini.
        #
        # Sampling behavior can be handled later through
        # system instructions when we harden the gateway.
        return await acompletion(**kwargs)

    # ---------------------------------------------------------
    # Cloudflare Workers AI
    # ---------------------------------------------------------
    if model.startswith("cloudflare/"):
        kwargs["api_key"] = get_required_env(
            "CLOUDFLARE_API_TOKEN"
        )

        kwargs["account_id"] = get_required_env(
            "CLOUDFLARE_ACCOUNT_ID"
        )

        if temperature is not None:
            kwargs["temperature"] = temperature

        return await acompletion(**kwargs)

    # ---------------------------------------------------------
    # Cohere
    # ---------------------------------------------------------
    if model.startswith("cohere/"):
        kwargs["api_key"] = get_required_env(
            "COHERE_API_KEY"
        )

        if temperature is not None:
            kwargs["temperature"] = temperature

        return await acompletion(**kwargs)

    raise ValueError(
        f"Unsupported model provider for model: {model}"
    )


async def call_gemini(
    messages: list[dict[str, str]],
    model: str = "gemini/gemini-3.6-flash",
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    return await call_model(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def call_cloudflare(
    messages: list[dict[str, str]],
    model: str = (
        "cloudflare/"
        "@cf/meta/llama-3.1-8b-instruct-fp8"
    ),
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    return await call_model(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )


async def call_cohere(
    messages: list[dict[str, str]],
    model: str = "cohere/command-a-plus-05-2026",
    temperature: float | None = None,
    max_tokens: int | None = None,
):
    return await call_model(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )