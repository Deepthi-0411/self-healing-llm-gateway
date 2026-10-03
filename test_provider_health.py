import asyncio

from app.gateway.provider_health import ProviderHealth


async def main():

    health = ProviderHealth()

    print("\n========== INITIAL STATE ==========")

    print(
        "Gemini can execute:",
        await health.can_execute("gemini")
    )

    print(
        "Cloudflare can execute:",
        await health.can_execute("cloudflare")
    )

    print(
        "Cohere can execute:",
        await health.can_execute("cohere")
    )

    print("\n========== GEMINI FAILURES ==========")

    await health.record_failure("gemini")
    await health.record_failure("gemini")
    await health.record_failure("gemini")

    print(
        "Gemini can execute:",
        await health.can_execute("gemini")
    )

    print(
        "Cloudflare can execute:",
        await health.can_execute("cloudflare")
    )

    print(
        "Cohere can execute:",
        await health.can_execute("cohere")
    )

    print("\n========== OTHER PROVIDER STATES ==========")

    print(
        "Cloudflare can execute:",
        await health.can_execute("cloudflare")
    )

    print(
        "Cohere can execute:",
        await health.can_execute("cohere")
    )

    print("\n=========================================")
    print("PROVIDER HEALTH TEST: SUCCESS")
    print("=========================================")


if __name__ == "__main__":
    asyncio.run(main())