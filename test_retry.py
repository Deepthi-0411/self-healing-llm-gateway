import asyncio

from app.gateway.retry import call_with_retry


class RateLimitError(Exception):
    pass


async def fake_provider(
        messages, 
        temperature=1,
        max_tokens=None
):

    print("[FakeProvider] Called")

    raise RateLimitError(
        "Simulated 429 rate limit"
    )


async def main():

    messages = [
        {
            "role": "user",
            "content": "Test retry mechanism"
        }
    ]

    try:

        await call_with_retry(
            call_function=fake_provider,
            messages=messages,
            temperature=1
        )

    except Exception as error:

        print("\n[Test] Final exception:")
        print(type(error).__name__)
        print(error)


if __name__ == "__main__":
    asyncio.run(main())