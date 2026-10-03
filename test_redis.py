import asyncio

from app.infra.redis_client import redis_client


async def main():
    print(
        "\n========== REDIS READ/WRITE TEST ==========\n"
    )

    test_key = "gateway:test"

    await redis_client.set(
        test_key,
        "hello-redis",
    )

    value = await redis_client.get(
        test_key
    )

    print("Written value:", "hello-redis")
    print("Read value:", value)

    if value == "hello-redis":
        print("\nRedis read/write: SUCCESS")
    else:
        print("\nRedis read/write: FAILED")

    await redis_client.delete(
        test_key
    )

    await redis_client.aclose()

    print(
        "\n===========================================\n"
    )


if __name__ == "__main__":
    asyncio.run(main())