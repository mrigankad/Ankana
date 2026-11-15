"""Model ids, routing tiers and the price table used for cost reporting."""

from dataclasses import dataclass

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"

MAX_TOOL_ROUNDS = 6
MAX_OUTPUT_TOKENS = 2500


@dataclass(frozen=True)
class Price:
    """USD per million tokens (first-party API list prices, cached 2026-11-03)."""

    input: float
    output: float
    cache_read: float
    cache_write: float  # 5 minute ephemeral write = 1.25x input


PRICES: dict[str, Price] = {
    HAIKU: Price(0.10, 0.50, 0.01, 0.125),
    SONNET: Price(2.00, 10.00, 0.10, 2.50),
    OPUS: Price(4.00, 20.00, 0.20, 5.00),
}

# Rs per USD used in the research memo.
INR_PER_USD = 88.0


def cost_usd(model: str, usage: dict) -> float:
    """Cost of one provider call from a usage dict; 0.0 for unpriced models."""
    price = PRICES.get(model)
    if price is None:
        return 0.0
    return (
        usage.get("input_tokens", 0) * price.input
        + usage.get("output_tokens", 0) * price.output
        + usage.get("cache_read_input_tokens", 0) * price.cache_read
        + usage.get("cache_creation_input_tokens", 0) * price.cache_write
    ) / 1_000_000
