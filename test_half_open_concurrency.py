import asyncio
import json
import os

import httpx
from dotenv import load_dotenv

load_dotenv()


def get_gateway_api_key() -> str:

    raw_keys = os.getenv(
        "GATEWAY_API_KEYS_JSON"
    )

    if not raw_keys:
        raise RuntimeError(
            "GATEWAY_API_KEYS_JSON is not configured."
        )

    api_keys = json.loads(raw_keys)

    if not api_keys:
        raise RuntimeError(
            "GATEWAY_API_KEYS_JSON is empty."
        )

    return next(iter(api_keys.values()))

URL = "http://127.0.0.1:8000/v1/chat/completions"


REQUEST_BODY = {
    "model": "gateway-default",
    "messages": [
        {
            "role": "user",
            "content": "Explain what an AI agent is in one sentence."
        }
    ],
    "temperature": 0.2,
    "metadata": {
        "tenant": "learning-platform",
        "feature": "ai-tutor",
        "request_id": "half-open-concurrency-test"
    }
}


async def send_request(
    client: httpx.AsyncClient,
    request_number: int
):

    body = REQUEST_BODY.copy()

    body["metadata"] = {
        **REQUEST_BODY["metadata"],
        "request_id": (
            f"half-open-concurrency-{request_number}"
        ),
    }

    try:

        response = await client.post(
            URL,
            json=body,
            headers={
                "Authorization": (
                    f"Bearer {get_gateway_api_key()}"
                )
            },
        )

        print(
            f"Request {request_number}: "
            f"HTTP {response.status_code}"
            f"{response.text}"
        )

        return response.status_code

    except Exception as exc:

        print(
            f"Request {request_number}: "
            f"ERROR - {type(exc).__name__}: {exc}"
        )

        return None


async def main():

    async with httpx.AsyncClient(
        timeout=30.0
    ) as client:

        tasks = [
            send_request(
                client,
                request_number
            )
            for request_number in range(1, 6)
        ]

        results = await asyncio.gather(
            *tasks
        )

        print("\nResults:")
        print(results)


if __name__ == "__main__":
    asyncio.run(main())