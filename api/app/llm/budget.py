"""Monthly LLM budget cap tracking per PRD Section 9.6 and NFR-041."""

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.analytics import LLMCall

logger = logging.getLogger("fridgechef.llm.budget")

# Groq model pricing per 1,000,000 tokens (USD): (prompt_cost_per_million, completion_cost_per_million)
MODEL_PRICING_PER_MILLION: dict[str, tuple[float, float]] = {
    "llama-3.3-70b-versatile": (0.59, 0.79),
    "meta-llama/llama-4-scout-17b-16e-instruct": (0.15, 0.60),
}
DEFAULT_PRICING_PER_MILLION: tuple[float, float] = (0.59, 0.79)


def calculate_call_cost_usd(model: str, prompt_tokens: int | None, completion_tokens: int | None) -> float:
    """Calculate USD cost of an LLM call based on token usage."""
    p_price, c_price = MODEL_PRICING_PER_MILLION.get(model, DEFAULT_PRICING_PER_MILLION)
    p_tok = prompt_tokens or 0
    c_tok = completion_tokens or 0
    cost = (p_tok / 1_000_000.0) * p_price + (c_tok / 1_000_000.0) * c_price
    return cost


def get_monthly_llm_spend_usd(db: Session, now: datetime | None = None) -> float:
    """Sum token costs in llm_calls for the current calendar month in USD."""
    if now is None:
        now = datetime.now(timezone.utc)

    # First day of the current month in UTC
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    calls = (
        db.query(LLMCall)
        .filter(
            LLMCall.created_at >= start_of_month,
            LLMCall.status == "OK",
        )
        .all()
    )

    total_spend = 0.0
    for call in calls:
        cost = calculate_call_cost_usd(call.model, call.prompt_tokens, call.completion_tokens)
        total_spend += cost

    return round(total_spend, 6)


def is_llm_budget_exceeded(db: Session, budget_usd: float | None, now: datetime | None = None) -> bool:
    """Check if current monthly spend has reached or exceeded 80% of LLM_MONTHLY_BUDGET_USD.

    Returns True if AI generation should be disabled per PRD Section 9.6.
    """
    if budget_usd is None or budget_usd <= 0.0:
        return False

    current_spend = get_monthly_llm_spend_usd(db, now)
    threshold = 0.80 * budget_usd

    if current_spend >= threshold:
        logger.warning(
            f"Monthly LLM spend (${current_spend:.4f}) reached or exceeded 80% of budget (${budget_usd:.2f}, threshold ${threshold:.4f}). "
            "Disabling AI recipe generation fallback."
        )
        return True

    return False
