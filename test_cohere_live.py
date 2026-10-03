import os
import asyncio

from dotenv import load_dotenv
from litellm import acompletion


load_dotenv()


async def main():

    print("\n========== COHERE LIVE TEST ==========\n")

    print(
        "Cohere API key loaded:",
        bool(os.getenv("COHERE_API_KEY"))
    )

    try:

        response = await acompletion(
            model="cohere_chat/command-a-plus-05-2026",
            messages=[
                {
                    "role": "user",
                    "content": "Say hello in one sentence."
                }
            ],
            max_tokens=30,
        )

        print("SUCCESS")
        print("Model:", response.model)

        print(
            "Response:",
            response.choices[0].message.content
        )

    except Exception as exc:

        print("FAILED")
        print(
            "Exception:",
            type(exc).__name__
        )
        print(
            "Error:",
            str(exc)
        )

    print("\n======================================\n")


if __name__ == "__main__":
    asyncio.run(main())