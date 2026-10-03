import asyncio

from app.llm.client import (
    call_model,
    call_gemini,
    call_cloudflare,
    call_cohere,
)


async def main():
    print("\n========== DYNAMIC CLIENT TEST ==========\n")

    test_messages = [
        {
            "role": "user",
            "content": "Say hello in one sentence.",
        }
    ]

    # --------------------------------------------------
    # 1. Test Gemini client configuration
    # --------------------------------------------------
    print("Testing Gemini client routing...")

    try:
        gemini_response = await call_gemini(
            messages=test_messages,
            model="gemini/gemini-3.6-flash",
            temperature=1,
        )

        print("Gemini: SUCCESS")
        print("Gemini response model:", gemini_response.model)

    except Exception as error:
        print("Gemini: PROVIDER ERROR")
        print(type(error).__name__)
        print("Reason:", str(error)[:300])

    # --------------------------------------------------
    # 2. Test Cloudflare client configuration
    # --------------------------------------------------
    print("\nTesting Cloudflare client routing...")

    try:
        cloudflare_response = await call_cloudflare(
            messages=test_messages,
            model="cloudflare/@cf/meta/llama-3.1-8b-instruct-fp8",
            temperature=0.2,
        )

        print("Cloudflare: SUCCESS")
        print(
            "Cloudflare response model:",
            cloudflare_response.model,
        )

    except Exception as error:
        print("Cloudflare: PROVIDER ERROR")
        print(type(error).__name__)
        print("Reason:", str(error)[:300])

    # --------------------------------------------------
    # 3. Test Cohere client configuration
    # --------------------------------------------------
    print("\nTesting Cohere client routing...")

    try:
        cohere_response = await call_cohere(
            messages=test_messages,
            model="cohere/command-a-plus-05-2026",
            temperature=0.2,
        )

        print("Cohere: SUCCESS")
        print(
            "Cohere response model:",
            cohere_response.model,
        )

    except Exception as error:
        print("Cohere: PROVIDER ERROR")
        print(type(error).__name__)
        print("Reason:", str(error)[:300])

    # --------------------------------------------------
    # 4. Verify unsupported provider handling
    # --------------------------------------------------
    print("\nTesting unsupported provider handling...")

    try:
        await call_model(
            model="unsupported/test-model",
            messages=test_messages,
        )

    except ValueError as error:
        print("Unsupported provider: SUCCESS")
        print("Error:", error)

    print("\n=========================================\n")


if __name__ == "__main__":
    asyncio.run(main())