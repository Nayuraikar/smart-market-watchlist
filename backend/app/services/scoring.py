"""Pure scoring functions. No DB, no provider, no FastAPI.
Per BUILD_ROADMAP.md Phase 6: 'never mixed with I/O.'

Two-layer design:
  1. compute_percentile_rank() — generic, no financial semantics at all.
     Ranks one value against a population. Used once per metric across
     the whole seeded instrument universe by a caller this module does
     not define (that caller also does the cross-table joins for P/E
     and FCF yield — see DECISIONS.md Phase 6.7).
  2. calculate_growth_score / calculate_value_score / calculate_stability_score
     — each consumes ONLY already-computed percentiles (dict[str, Decimal | None]),
     never raw metric values. Weights and directions are frozen from
     SCORING_MODEL.md and must not drift from it.

INSUFFICIENT_DATA is returned, never fabricated, when available weight
coverage for an objective falls below the 60% threshold confirmed in
SCORING_MODEL.md.
"""

from decimal import Decimal
from typing import Literal

INSUFFICIENT_DATA: Literal["INSUFFICIENT_DATA"] = "INSUFFICIENT_DATA"
ScoreResult = Decimal | Literal["INSUFFICIENT_DATA"]

MIN_COVERAGE_PCT = Decimal("60")

# Frozen from SCORING_MODEL.md. Do not edit here — edit the doc first.
GROWTH_METRICS: dict[str, tuple[Decimal, str]] = {
    "revenue_growth": (Decimal("40"), "higher_better"),
    "eps_growth": (Decimal("40"), "higher_better"),
    "roce": (Decimal("20"), "higher_better"),
}

VALUE_METRICS: dict[str, tuple[Decimal, str]] = {
    "pe_ratio": (Decimal("40"), "lower_better"),
    "pb_ratio": (Decimal("30"), "lower_better"),   # always missing — see DECISIONS.md
    "fcf_yield": (Decimal("30"), "higher_better"),
}

STABILITY_METRICS: dict[str, tuple[Decimal, str]] = {
    "debt_to_equity": (Decimal("40"), "lower_better"),
    "roe": (Decimal("30"), "higher_better"),
    "earnings_volatility": (Decimal("30"), "lower_better"),  # deferred — always missing
}


def compute_percentile_rank(value: Decimal, population: list[Decimal]) -> Decimal | None:
    """Generic percentile rank of `value` within `population`, 0-100 scale.
    No financial semantics, no direction handling — that's the score
    functions' job, not this function's.

    Ties are given the midpoint rank: a value tied with k other members
    of an n-element population ranks as (values_below + k/2) / n * 100,
    not arbitrarily broken by insertion order. A population of a single
    element equal to the value ranks at exactly 50 (neither highest nor
    lowest possible), not 0 or 100.

    Returns None for an empty population — never a fabricated midpoint
    when there's nothing to rank against. Caller is responsible for
    excluding None/null values from `population` before calling this;
    this function does not know what a "null metric" means, it just
    ranks whatever Decimals it's given.
    """
    if not population:
        return None

    n = len(population)
    below = sum(1 for p in population if p < value)
    equal = sum(1 for p in population if p == value)

    return (Decimal(below) + Decimal(equal) / 2) / Decimal(n) * 100


def compute_fcf_yield(free_cash_flow: Decimal | None, market_cap: Decimal | None) -> Decimal | None:
    """FCF yield = free_cash_flow / market_cap. Derived at the scoring-
    input-prep layer per DECISIONS.md Phase 6.7 — FCF lives on
    FundamentalSnapshot, market_cap lives on MarketObservation, neither
    table stores this ratio directly. None if either leg is missing or
    market_cap is zero, never a fabricated yield."""
    if free_cash_flow is None or market_cap is None or market_cap == 0:
        return None
    return free_cash_flow / market_cap


def _score_from_percentiles(
    metrics: dict[str, tuple[Decimal, str]],
    percentiles: dict[str, Decimal | None],
    min_coverage_pct: Decimal = MIN_COVERAGE_PCT,
) -> ScoreResult:
    """Shared weighting/renormalization/coverage logic for all three
    objectives. Takes the frozen (weight, direction) table for one
    objective plus a dict of already-computed percentiles (0-100 scale,
    higher = better raw rank, direction-agnostic) keyed by metric name.

    A metric absent from `percentiles`, or present with value None, is
    treated identically: unavailable. Available weight is summed and
    checked against min_coverage_pct BEFORE renormalizing; renormalized
    weights are only ever computed across metrics that are actually
    available, and always sum to 100 among themselves.
    """
    total_weight = sum(w for w, _direction in metrics.values())

    available: dict[str, Decimal] = {}
    for metric_name, (weight, _direction) in metrics.items():
        value = percentiles.get(metric_name)
        if value is not None:
            available[metric_name] = weight

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
    """percentiles keys: revenue_growth, eps_growth, roce (any subset)."""
    return _score_from_percentiles(GROWTH_METRICS, percentiles)


def calculate_value_score(percentiles: dict[str, Decimal | None]) -> ScoreResult:
    """percentiles keys: pe_ratio, pb_ratio, fcf_yield (any subset).
    pb_ratio should always be None/absent per DECISIONS.md Phase 6.7 —
    this function doesn't special-case that, it just treats it as
    missing like any other unavailable metric."""
    return _score_from_percentiles(VALUE_METRICS, percentiles)


def calculate_stability_score(percentiles: dict[str, Decimal | None]) -> ScoreResult:
    """percentiles keys: debt_to_equity, roe, earnings_volatility (any subset).
    earnings_volatility should always be None/absent per DECISIONS.md
    Phase 6.7 (deferred, no methodology defined) — this function
    doesn't special-case that either, same reasoning as pb_ratio above."""
    return _score_from_percentiles(STABILITY_METRICS, percentiles)
