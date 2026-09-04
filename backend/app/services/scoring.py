"""Pure scoring functions. No DB, no provider, no FastAPI.
Per BUILD_ROADMAP.md Phase 6: 'never mixed with I/O.'

Two-layer design:
  1. compute_percentile_rank() - generic, no financial semantics at all.
     Formula frozen in SCORING_MODEL.md: 100 x (average_rank - 1) / (n - 1),
     1-indexed ranks, ties share average rank, singleton population is
     always 50, out-of-range query values clamp to [0, 100]. Used once
     per metric across the whole seeded instrument universe by a caller
     this module does not define (that caller also does the cross-table
     joins for P/E and FCF yield - see DECISIONS.md Phase 6.7).
  2. calculate_growth_score / calculate_value_score / calculate_stability_score
     - each consumes ONLY already-computed percentiles (dict[str, Decimal | None]),
     never raw metric values. Weights and directions are frozen from
     SCORING_MODEL.md and must not drift from it. Every provided
     percentile must lie in [0, 100]; anything outside that range is a
     caller/data-contract bug and raises ValueError rather than being
     silently treated as missing data.
"""

from decimal import Decimal
from typing import Literal

INSUFFICIENT_DATA: Literal["INSUFFICIENT_DATA"] = "INSUFFICIENT_DATA"
ScoreResult = Decimal | Literal["INSUFFICIENT_DATA"]

MIN_COVERAGE_PCT = Decimal("60")

GROWTH_METRICS: dict[str, tuple[Decimal, str]] = {
    "revenue_growth": (Decimal("40"), "higher_better"),
    "eps_growth": (Decimal("40"), "higher_better"),
    "roce": (Decimal("20"), "higher_better"),
}

VALUE_METRICS: dict[str, tuple[Decimal, str]] = {
    "pe_ratio": (Decimal("40"), "lower_better"),
    "pb_ratio": (Decimal("30"), "lower_better"),
    "fcf_yield": (Decimal("30"), "higher_better"),
}

STABILITY_METRICS: dict[str, tuple[Decimal, str]] = {
    "debt_to_equity": (Decimal("40"), "lower_better"),
    "roe": (Decimal("30"), "higher_better"),
    "earnings_volatility": (Decimal("30"), "lower_better"),
}


def compute_percentile_rank(value: Decimal, population: list[Decimal]) -> Decimal | None:
    """Frozen formula per SCORING_MODEL.md: 100 x (average_rank - 1) / (n - 1).
    Ranks 1-indexed ascending, ties share average rank. Lowest member -> 0,
    highest -> 100. Singleton population -> always 50. Out-of-range query
    values clamp to [0, 100]. Empty population -> None."""
    if not population:
        return None

    n = len(population)
    if n == 1:
        return Decimal("50")

    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)

    effective_rank = Decimal(below) + (Decimal(equal) + 1) / 2
    percentile = (effective_rank - 1) / (Decimal(n) - 1) * 100

    if percentile < 0:
        return Decimal("0")
    if percentile > 100:
        return Decimal("100")
    return percentile


def compute_fcf_yield(free_cash_flow: Decimal | None, market_cap: Decimal | None) -> Decimal | None:
    """FCF yield = (free_cash_flow / market_cap) x 100, as a percentage,
    consistent with revenue_growth/eps_growth-style metrics."""
    if free_cash_flow is None or market_cap is None or market_cap == 0:
        return None
    return (free_cash_flow / market_cap) * 100


def _validate_percentile(metric_name: str, value: Decimal) -> None:
    if not (Decimal("0") <= value <= Decimal("100")):
        raise ValueError(
            f"percentile for '{metric_name}' is {value}, outside [0, 100] - "
            "caller/data-contract bug, not a missing-data case."
        )


def _score_from_percentiles(
    metrics: dict[str, tuple[Decimal, str]],
    percentiles: dict[str, Decimal | None],
    min_coverage_pct: Decimal = MIN_COVERAGE_PCT,
) -> ScoreResult:
    total_weight = sum(w for w, _direction in metrics.values())

    available: dict[str, Decimal] = {}
    for metric_name in metrics:
        value = percentiles.get(metric_name)
        if value is not None:
            _validate_percentile(metric_name, value)
            available[metric_name] = metrics[metric_name][0]

    available_weight = sum(available.values()) if available else Decimal("0")
    coverage_pct = (available_weight / total_weight) * 100 if total_weight else Decimal("0")

    if coverage_pct < min_coverage_pct:
        return INSUFFICIENT_DATA

    score = Decimal("0")
    for metric_name, weight in available.items():
        _frozen_weight, direction = metrics[metric_name]
        raw_percentile = percentiles[metric_name]
        directional_percentile = (
            (Decimal("100") - raw_percentile) if direction == "lower_better" else raw_percentile
        )
        renormalized_weight = weight / available_weight
        score += renormalized_weight * directional_percentile

    return score


def calculate_growth_score(percentiles: dict[str, Decimal | None]) -> ScoreResult:
    return _score_from_percentiles(GROWTH_METRICS, percentiles)


def calculate_value_score(percentiles: dict[str, Decimal | None]) -> ScoreResult:
    return _score_from_percentiles(VALUE_METRICS, percentiles)


def calculate_stability_score(percentiles: dict[str, Decimal | None]) -> ScoreResult:
    return _score_from_percentiles(STABILITY_METRICS, percentiles)
