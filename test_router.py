import asyncio

from app.llm.router import call_with_fallback


async def main():
    messages = [
        {
            "role": "user",
            "content": "Explain what a database is in one sentence."
        }
    ]

    response = await call_with_fallback(messages)

    print("\n========== ROUTER TEST ==========")
    print(response.choices[0].message.content)
    print("=================================\n")


asyncio.run(main())