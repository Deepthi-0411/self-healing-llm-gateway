import json

import pytest
from fastapi import HTTPException

from app.gateway.auth import authenticate_request


@pytest.fixture
def configured_api_keys(monkeypatch):
    api_keys = {
        "learning-platform": "test-learning-key",
        "budget-runtime-test": "test-budget-key",
    }

    monkeypatch.setenv(
        "GATEWAY_API_KEYS_JSON",
        json.dumps(api_keys),
    )

    return api_keys


def test_missing_authorization(configured_api_keys):
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request(None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing Authorization header."


def test_invalid_authorization(configured_api_keys):
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request("Bearer invalid-key")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid gateway API key."


def test_invalid_authorization_format(configured_api_keys):
    with pytest.raises(HTTPException) as exc_info:
        authenticate_request("Basic test-key")

    assert exc_info.value.status_code == 401
    assert (
        exc_info.value.detail
        == "Authorization header must use Bearer authentication."
    )


def test_valid_authorization(configured_api_keys):
    tenant = authenticate_request(
        "Bearer test-learning-key"
    )

    assert tenant == "learning-platform"
