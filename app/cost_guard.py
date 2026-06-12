import time
import logging
from dataclasses import dataclass, field
from fastapi import HTTPException
import redis
from app.config import settings

logger = logging.getLogger(__name__)

# Mock token pricing (GPT-4o-mini rates as default)
PRICE_PER_1K_INPUT_TOKENS = 0.00015   # $0.15/1M input
PRICE_PER_1K_OUTPUT_TOKENS = 0.0006   # $0.60/1M output

@dataclass
class UsageRecord:
    user_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    request_count: int = 0
    day: str = field(default_factory=lambda: time.strftime("%Y-%m-%d"))

    @property
    def total_cost_usd(self) -> float:
        input_cost = (self.input_tokens / 1000) * PRICE_PER_1K_INPUT_TOKENS
        output_cost = (self.output_tokens / 1000) * PRICE_PER_1K_OUTPUT_TOKENS
        return round(input_cost + output_cost, 6)

class RedisCostGuard:
    def __init__(self, redis_client: redis.Redis | None = None, monthly_budget_usd: float = 10.0):
        self.r = redis_client
        self.monthly_budget_usd = monthly_budget_usd
        # In-memory fallback
        self._memory_store = {}

    def _get_month_key(self, user_id: str) -> str:
        month_str = time.strftime("%Y-%m")
        return f"cost:{user_id}:{month_str}"

    def check_budget(self, user_id: str, estimated_cost: float = 0.005) -> None:
        """
        Check if user has remaining budget.
        Raises 402 if budget exceeded.
        """
        # If Redis is connected
        if self.r is not None:
            try:
                key = self._get_month_key(user_id)
                current_cost = float(self.r.get(key) or 0)
                if current_cost + estimated_cost > self.monthly_budget_usd:
                    raise HTTPException(
                        status_code=402,
                        detail={
                            "error": "Monthly budget exceeded",
                            "used_usd": current_cost,
                            "budget_usd": self.monthly_budget_usd,
                        }
                    )
                return
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Redis budget check failed, falling back to memory: {e}")

        # In-memory fallback
        key = self._get_month_key(user_id)
        current_cost = self._memory_store.get(key, 0.0)
        if current_cost + estimated_cost > self.monthly_budget_usd:
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "Monthly budget exceeded (in-memory)",
                    "used_usd": current_cost,
                    "budget_usd": self.monthly_budget_usd,
                }
            )

    def record_usage(self, user_id: str, input_tokens: int, output_tokens: int) -> float:
        """
        Records the token usage, calculates cost, updates the budget, and returns the new total cost.
        """
        cost = (input_tokens / 1000 * PRICE_PER_1K_INPUT_TOKENS) + (output_tokens / 1000 * PRICE_PER_1K_OUTPUT_TOKENS)
        
        # Redis
        if self.r is not None:
            try:
                key = self._get_month_key(user_id)
                new_cost = self.r.incrbyfloat(key, cost)
                self.r.expire(key, 35 * 24 * 3600)  # Keep for 35 days
                logger.info(f"Recorded usage for {user_id}: +${cost:.6f}, total: ${new_cost:.6f}")
                return new_cost
            except Exception as e:
                logger.warning(f"Redis record usage failed, falling back to memory: {e}")

        # In-memory fallback
        key = self._get_month_key(user_id)
        current_cost = self._memory_store.get(key, 0.0)
        new_cost = current_cost + cost
        self._memory_store[key] = new_cost
        logger.info(f"Recorded usage (in-memory) for {user_id}: +${cost:.6f}, total: ${new_cost:.6f}")
        return new_cost

    def get_usage(self, user_id: str) -> dict:
        key = self._get_month_key(user_id)
        cost = 0.0
        
        if self.r is not None:
            try:
                cost = float(self.r.get(key) or 0.0)
            except Exception as e:
                logger.warning(f"Redis get_usage failed: {e}")
                cost = self._memory_store.get(key, 0.0)
        else:
            cost = self._memory_store.get(key, 0.0)

        return {
            "user_id": user_id,
            "cost_usd": round(cost, 6),
            "budget_usd": self.monthly_budget_usd,
            "budget_remaining_usd": round(max(0.0, self.monthly_budget_usd - cost), 6),
            "budget_used_pct": round((cost / self.monthly_budget_usd) * 100, 2) if self.monthly_budget_usd > 0 else 0.0
        }
