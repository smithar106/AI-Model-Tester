"""Public model pricing tables and cost helpers.

All prices are in USD per 1,000,000 tokens and reflect publicly listed
list pricing. Update the PRICING table as vendor pricing changes.
"""

from __future__ import annotations

# USD per 1M tokens.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.00, "output": 15.00},
    "deepseek-chat": {"input": 0.27, "output": 1.10},
}

DEFAULT_PRICE: dict[str, float] = {"input": 0.0, "output": 0.0}


def price_for(model: str) -> dict[str, float]:
    """Return the per-1M-token price for a model (zeros if unknown)."""
    return PRICING.get(model, DEFAULT_PRICE)


def cost_usd(model: str, input_tokens: float, output_tokens: float) -> float:
    """Compute the USD cost of a single call given token counts."""
    p = price_for(model)
    return (input_tokens / 1_000_000) * p["input"] + (output_tokens / 1_000_000) * p["output"]


def project_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    tokens_per_day: int,
) -> dict[str, object]:
    """Project daily / monthly / annual cost at a target token volume.

    The observed input:output ratio is used to split ``tokens_per_day`` into
    input and output tokens, then priced with the model's rate card.
    """
    total = input_tokens + output_tokens
    if total <= 0:
        in_ratio = out_ratio = 0.5
    else:
        in_ratio = input_tokens / total
        out_ratio = output_tokens / total

    daily_in = tokens_per_day * in_ratio
    daily_out = tokens_per_day * out_ratio
    daily = cost_usd(model, daily_in, daily_out)

    return {
        "model": model,
        "tokens_per_day": tokens_per_day,
        "input_output_ratio": f"{in_ratio * 100:.0f}/{out_ratio * 100:.0f}",
        "daily_cost": round(daily, 2),
        "monthly_cost": round(daily * 30, 2),
        "annual_cost": round(daily * 365, 2),
    }
