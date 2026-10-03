from dataclasses import dataclass
from datetime import datetime, timezone

from app.gateway.request_logger import log_event
from app.infra.redis_client import redis_client
from app.llm.tiering import ModelTier


# ============================================================
# BUDGET RESULT
# ============================================================

@dataclass
class BudgetResult:
    allowed: bool
    limit: int
    used: int
    remaining: int
    requested: int
    reset_after: int


# ============================================================
# REDIS BUDGET MANAGER
# ============================================================

class RedisBudgetManager:

    def __init__(self, default_budget=100):
        self.default_budget = default_budget

        # ----------------------------------------------------
        # Tenant-specific monthly budgets
        # ----------------------------------------------------

        self.tenant_budgets = {
            "learning-platform": 100,
            "budget-demo": 5,
        }

        # ----------------------------------------------------
        # Atomic Redis budget script
        # ----------------------------------------------------

        self._consume_script = redis_client.register_script(
            """
            local current = redis.call(
                'GET',
                KEYS[1]
            )

            if not current then
                current = 0
            else
                current = tonumber(current)
            end

            local limit = tonumber(ARGV[1])
            local requested = tonumber(ARGV[2])
            local ttl = tonumber(ARGV[3])

            if current + requested > limit then
                return {
                    0,
                    current,
                    math.max(
                        limit - current,
                        0
                    )
                }
            end

            local new_value = redis.call(
                'INCRBY',
                KEYS[1],
                requested
            )

            local existing_ttl = redis.call(
                'TTL',
                KEYS[1]
            )

            if existing_ttl < 0 then
                redis.call(
                    'EXPIRE',
                    KEYS[1],
                    ttl
                )
            end

            return {
                1,
                new_value,
                math.max(
                    limit - new_value,
                    0
                )
            }
            """
        )

    # ========================================================
    # GET TENANT BUDGET
    # ========================================================

    def get_budget(self, tenant):
        return self.tenant_budgets.get(
            tenant,
            self.default_budget,
        )

    # ========================================================
    # TIER -> COST
    # ========================================================

    def get_cost(self, tier: ModelTier) -> int:

        if tier == ModelTier.SMALL:
            return 1

        if tier == ModelTier.MEDIUM:
            return 2

        if tier == ModelTier.LARGE:
            return 4

        raise ValueError(
            f"Unsupported model tier: {tier}"
        )

    # ========================================================
    # CURRENT UTC MONTH
    # ========================================================

    def get_month_key(self):

        now = datetime.now(
            timezone.utc
        )

        return now.strftime(
            "%Y-%m"
        )

    # ========================================================
    # BUILD REDIS BUDGET KEY
    # ========================================================

    def get_budget_key(
        self,
        tenant,
        month=None,
    ):
        if month is None:
            month = self.get_month_key()

        return (
            f"gateway:budget:"
            f"{tenant}:"
            f"{month}:units"
        )

    # ========================================================
    # SECONDS UNTIL NEXT MONTH
    # ========================================================

    def get_seconds_until_next_month(self) -> int:

        now = datetime.now(
            timezone.utc
        )

        if now.month == 12:
            next_month = datetime(
                now.year + 1,
                1,
                1,
                tzinfo=timezone.utc,
            )
        else:
            next_month = datetime(
                now.year,
                now.month + 1,
                1,
                tzinfo=timezone.utc,
            )

        seconds = (
            next_month - now
        ).total_seconds()

        return max(
            int(seconds),
            1,
        )

    # ========================================================
    # CHECK + CONSUME BUDGET
    # ========================================================

    async def check_and_consume(
        self,
        tenant,
        tier: ModelTier,
    ) -> BudgetResult:

        # ----------------------------------------------------
        # Determine tenant budget
        # ----------------------------------------------------

        limit = self.get_budget(
            tenant
        )

        # ----------------------------------------------------
        # Determine logical cost
        # ----------------------------------------------------

        requested = self.get_cost(
            tier
        )

        # ----------------------------------------------------
        # Current UTC month
        # ----------------------------------------------------

        month = self.get_month_key()

        # ----------------------------------------------------
        # Redis key
        # ----------------------------------------------------

        key = self.get_budget_key(
            tenant=tenant,
            month=month,
        )

        # ----------------------------------------------------
        # Reset time
        # ----------------------------------------------------

        reset_after = (
            self.get_seconds_until_next_month()
        )

        # ----------------------------------------------------
        # Atomic check + increment
        # ----------------------------------------------------

        result = await self._consume_script(
            keys=[key],
            args=[
                limit,
                requested,
                reset_after,
            ],
        )

        allowed = (
            int(result[0]) == 1
        )

        used = int(
            result[1]
        )

        remaining = int(
            result[2]
        )

        # ----------------------------------------------------
        # Structured budget log
        # ----------------------------------------------------

        log_event(
            "budget_checked",
            tenant=tenant,
            tier=tier.value,
            requested=requested,
            limit=limit,
            used=used,
            remaining=remaining,
            allowed=allowed,
            reset_after=reset_after,
        )

        # ----------------------------------------------------
        # Structured rejection log
        # ----------------------------------------------------

        if not allowed:

            log_event(
                "budget_exceeded",
                level="WARNING",
                tenant=tenant,
                tier=tier.value,
                requested=requested,
                limit=limit,
                used=used,
                remaining=remaining,
                reset_after=reset_after,
            )

        return BudgetResult(
            allowed=allowed,
            limit=limit,
            used=used,
            remaining=remaining,
            requested=requested,
            reset_after=reset_after,
        )


# ============================================================
# GLOBAL BUDGET MANAGER
# ============================================================

budget_manager = RedisBudgetManager(
    default_budget=100,
)