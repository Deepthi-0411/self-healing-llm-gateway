import os
import asyncio

from dotenv import load_dotenv
from litellm import acompletion


load_dotenv()


async def main():

    print("\n========== CLOUDFLARE LIVE TEST ==========\n")

    api_token = os.getenv("CLOUDFLARE_API_TOKEN")
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")

    print(
        "Cloudflare API token loaded:",
        bool(api_token)
    )

    print(
        "Cloudflare Account ID loaded:",
        bool(account_id)
    )

    try:

        response = await acompletion(
            model="cloudflare/@cf/meta/llama-3.1-8b-instruct-fp8",
            api_key=api_token,
            account_id=account_id,
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

    print("\n===========================================\n")


if __name__ == "__main__":
    asyncio.run(main())