import asyncio

from app.gateway.budget import (
    RedisBudgetManager,
)
from app.infra.redis_client import (
    redis_client,
)
from app.llm.tiering import ModelTier


async def main():

    print(
        "\n========================================="
    )

    print(
        "REDIS BUDGET TEST"
    )

    print(
        "=========================================\n"
    )

    manager = RedisBudgetManager(
        default_budget=5,
    )

    tenant = "budget-test-tenant"

    # --------------------------------------------------------
    # Clean this month's test key
    # --------------------------------------------------------

    key = manager.get_budget_key(
        tenant
    )

    await redis_client.delete(
        key
    )

    # --------------------------------------------------------
    # SMALL = 1
    # --------------------------------------------------------

    result = await manager.check_and_consume(
        tenant=tenant,
        tier=ModelTier.SMALL,
    )

    print(
        "[TEST] SMALL allowed:",
        result.allowed,
    )

    print(
        "[TEST] Used:",
        result.used,
    )

    print(
        "[TEST] Remaining:",
        result.remaining,
    )

    assert result.allowed is True
    assert result.used == 1
    assert result.remaining == 4

    # --------------------------------------------------------
    # MEDIUM = 2
    # --------------------------------------------------------

    result = await manager.check_and_consume(
        tenant=tenant,
        tier=ModelTier.MEDIUM,
    )

    print(
        "\n[TEST] MEDIUM allowed:",
        result.allowed,
    )

    print(
        "[TEST] Used:",
        result.used,
    )

    print(
        "[TEST] Remaining:",
        result.remaining,
    )

    assert result.allowed is True
    assert result.used == 3
    assert result.remaining == 2

    # --------------------------------------------------------
    # LARGE = 4
    #
    # 3 + 4 = 7
    # Budget = 5
    # Therefore reject.
    # --------------------------------------------------------

    result = await manager.check_and_consume(
        tenant=tenant,
        tier=ModelTier.LARGE,
    )

    print(
        "\n[TEST] LARGE allowed:",
        result.allowed,
    )

    print(
        "[TEST] Used:",
        result.used,
    )

    print(
        "[TEST] Remaining:",
        result.remaining,
    )

    assert result.allowed is False
    assert result.used == 3
    assert result.remaining == 2

    # --------------------------------------------------------
    # SMALL = 1
    # 3 + 1 = 4
    # --------------------------------------------------------

    result = await manager.check_and_consume(
        tenant=tenant,
        tier=ModelTier.SMALL,
    )

    print(
        "\n[TEST] SMALL #2 allowed:",
        result.allowed,
    )

    print(
        "[TEST] Used:",
        result.used,
    )

    print(
        "[TEST] Remaining:",
        result.remaining,
    )

    assert result.allowed is True
    assert result.used == 4
    assert result.remaining == 1

    # --------------------------------------------------------
    # SMALL = 1
    # 4 + 1 = 5
    # Exactly reaches budget.
    # --------------------------------------------------------

    result = await manager.check_and_consume(
        tenant=tenant,
        tier=ModelTier.SMALL,
    )

    print(
        "\n[TEST] SMALL #3 allowed:",
        result.allowed,
    )

    print(
        "[TEST] Used:",
        result.used,
    )

    print(
        "[TEST] Remaining:",
        result.remaining,
    )

    assert result.allowed is True
    assert result.used == 5
    assert result.remaining == 0

    # --------------------------------------------------------
    # Another SMALL should fail.
    # --------------------------------------------------------

    result = await manager.check_and_consume(
        tenant=tenant,
        tier=ModelTier.SMALL,
    )

    print(
        "\n[TEST] Final SMALL allowed:",
        result.allowed,
    )

    print(
        "[TEST] Used:",
        result.used,
    )

    print(
        "[TEST] Remaining:",
        result.remaining,
    )

    assert result.allowed is False
    assert result.used == 5
    assert result.remaining == 0

    print(
        "\n========================================="
    )

    print(
        "REDIS BUDGET TEST: SUCCESS"
    )

    print(
        "=========================================\n"
    )

    await redis_client.delete(
        key
    )

    await redis_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())