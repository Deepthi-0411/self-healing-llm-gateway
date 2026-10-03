import pytest

from app.llm.client import call_model


@pytest.mark.anyio
async def test_unsupported_provider():
    messages = [
        {
            "role": "user",
            "content": "Hello"
        }
    ]

    with pytest.raises(
        ValueError,
        match="Unsupported model provider"
    ):
        await call_model(
            model="unknown/test-model",
            messages=messages,
        )

from unittest.mock import AsyncMock, patch


@pytest.mark.anyio
async def test_gemini_provider_routing():
    messages = [
        {
            "role": "user",
            "content": "Hello"
        }
    ]

    fake_response = {
        "model": "gemini/gemini-3.6-flash"
    }

    with patch(
        "app.llm.client.acompletion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ) as mock_completion:

        await call_model(
            model="gemini/gemini-3.6-flash",
            messages=messages,
        )

        mock_completion.assert_awaited_once()

        call_kwargs = mock_completion.await_args.kwargs

        assert call_kwargs["model"] == "gemini/gemini-3.6-flash"
        assert call_kwargs["messages"] == messages

@pytest.mark.anyio
async def test_cloudflare_provider_routing():
    messages = [
        {
            "role": "user",
            "content": "Hello"
        }
    ]

    fake_response = {
        "model": "cloudflare/@cf/meta/llama-3.1-8b-instruct-fp8"
    }

    with patch(
        "app.llm.client.acompletion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ) as mock_completion:

        with patch(
            "app.llm.client.get_required_env",
            side_effect=lambda name: {
                "CLOUDFLARE_API_TOKEN": "test-token",
                "CLOUDFLARE_ACCOUNT_ID": "test-account",
            }[name],
        ):

            await call_model(
                model="cloudflare/@cf/meta/llama-3.1-8b-instruct-fp8",
                messages=messages,
            )

        mock_completion.assert_awaited_once()

        call_kwargs = mock_completion.await_args.kwargs

        assert (
            call_kwargs["model"]
            == "cloudflare/@cf/meta/llama-3.1-8b-instruct-fp8"
        )

        assert call_kwargs["messages"] == messages

        assert call_kwargs["api_key"] == "test-token"
        assert call_kwargs["account_id"] == "test-account"

@pytest.mark.anyio
async def test_cohere_provider_routing():
    messages = [
        {
            "role": "user",
            "content": "Hello"
        }
    ]

    fake_response = {
        "model": "cohere/command-a-plus-05-2026"
    }

    with patch(
        "app.llm.client.acompletion",
        new_callable=AsyncMock,
        return_value=fake_response,
    ) as mock_completion:

        with patch(
            "app.llm.client.get_required_env",
            return_value="test-cohere-key",
        ):

            await call_model(
                model="cohere/command-a-plus-05-2026",
                messages=messages,
            )

        mock_completion.assert_awaited_once()

        call_kwargs = mock_completion.await_args.kwargs

        assert (
            call_kwargs["model"]
            == "cohere/command-a-plus-05-2026"
        )

        assert call_kwargs["messages"] == messages

        assert call_kwargs["api_key"] == "test-cohere-key"