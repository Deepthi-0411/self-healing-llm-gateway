import hmac
import json
import os

from fastapi import Header, HTTPException
from dotenv import load_dotenv

load_dotenv()


def _load_api_keys() -> dict[str, str]:
    raw_keys = os.getenv("GATEWAY_API_KEYS_JSON")

    if not raw_keys:
        raise RuntimeError(
            "GATEWAY_API_KEYS_JSON is not configured."
        )

    try:
        api_keys = json.loads(raw_keys)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "GATEWAY_API_KEYS_JSON must contain valid JSON."
        ) from error

    if not isinstance(api_keys, dict) or not api_keys:
        raise RuntimeError(
            "GATEWAY_API_KEYS_JSON must be a non-empty JSON object."
        )

    return api_keys


def authenticate_request(
    authorization: str | None = Header(default=None),
) -> str:
    """
    Validate the gateway API key and return the authenticated tenant.
    """

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing Authorization header.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Authorization header must use Bearer authentication.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_key = authorization.removeprefix("Bearer ").strip()

    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="Bearer token is empty.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    api_keys = _load_api_keys()

    for tenant, configured_key in api_keys.items():
        if hmac.compare_digest(
            api_key,
            configured_key,
        ):
            return tenant

    raise HTTPException(
        status_code=401,
        detail="Invalid gateway API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )