import asyncio

from app.llm.client import call_gemini


async def main():
    messages = [
        {
            "role": "user",
            "content": "Explain what an API is in one sentence.",
        }
    ]

    print("\n========== GEMINI PROVIDER TEST ==========\n")

    response = await call_gemini(
        messages=messages,
        model="gemini/gemini-3.6-flash",
        temperature=1,
    )

    print("Model:", response.model)
    print("Response:", response.choices[0].message.content)

    print("\n==========================================\n")


if __name__ == "__main__":
    asyncio.run(main())