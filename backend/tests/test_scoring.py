import pytest
from decimal import Decimal

from app.services.scoring import (
    compute_percentile_rank, compute_fcf_yield,
    calculate_growth_score, calculate_value_score, calculate_stability_score,
    INSUFFICIENT_DATA,
)


# ---- compute_percentile_rank: frozen formula, 100 x (avg_rank-1)/(n-1) ----

def test_percentile_rank_median_of_five():
    population = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]
    # below=2, equal=1 -> effective_rank=2+1=3 -> 100*(3-1)/(5-1)=50
    assert compute_percentile_rank(Decimal("30"), population) == Decimal("50")


def test_percentile_rank_highest_value_maps_to_100():
    population = [Decimal("10"), Decimal("20"), Decimal("30")]
    # below=2, equal=1 -> effective_rank=3 -> 100*(3-1)/(3-1)=100
    assert compute_percentile_rank(Decimal("30"), population) == Decimal("100")


def test_percentile_rank_lowest_value_maps_to_0():
    population = [Decimal("10"), Decimal("20"), Decimal("30")]
    # below=0, equal=1 -> effective_rank=1 -> 100*(1-1)/(3-1)=0
    assert compute_percentile_rank(Decimal("10"), population) == Decimal("0")


def test_percentile_rank_ties_share_average_rank():
    """Three-way tie occupying the lowest 3 of 5 positions (ranks 1,2,3,
    average rank 2). below=0, equal=3 -> effective_rank=0+(3+1)/2=2
    -> 100*(2-1)/(5-1)=25."""
    population = [Decimal("50"), Decimal("50"), Decimal("50"), Decimal("60"), Decimal("70")]
    assert compute_percentile_rank(Decimal("50"), population) == Decimal("25")


def test_percentile_rank_singleton_population_always_50():
    """Singleton population -> always 50, even when the query value
    doesn't match the sole member — there is no relative position to
    report either way."""
    assert compute_percentile_rank(Decimal("100"), [Decimal("100")]) == Decimal("50")
    assert compute_percentile_rank(Decimal("999"), [Decimal("100")]) == Decimal("50")


def test_percentile_rank_empty_population_none():
    assert compute_percentile_rank(Decimal("100"), []) is None


def test_percentile_rank_value_between_population_members():
    """Value not a literal population member, falls strictly between two
    members. population=[10,20,30,40,50], value=35: below=3 (10,20,30),
    equal=0 -> effective_rank=3.5 -> 100*(3.5-1)/(5-1)=62.5."""
    population = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]
    assert compute_percentile_rank(Decimal("35"), population) == Decimal("62.5")


def test_percentile_rank_value_below_population_min_clamps_to_0():
    """Value below every member: below=0, equal=0 -> effective_rank=0.5
    -> raw = 100*(0.5-1)/(5-1) = -12.5, clamped to 0."""
    population = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]
    assert compute_percentile_rank(Decimal("5"), population) == Decimal("0")


def test_percentile_rank_value_above_population_max_clamps_to_100():
    """Value above every member: below=5, equal=0 -> effective_rank=5.5
    -> raw = 100*(5.5-1)/(5-1) = 112.5, clamped to 100."""
    population = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]
    assert compute_percentile_rank(Decimal("60"), population) == Decimal("100")


# ---- compute_fcf_yield: derived cross-table metric, percentage scale ----

def test_fcf_yield_returns_percentage_not_raw_ratio():
    """10% yield must return 10, not 0.1 — consistent with every other
    percentage-style metric in the system (see DECISIONS.md)."""
    assert compute_fcf_yield(Decimal("1000000"), Decimal("10000000")) == Decimal("10")


def test_fcf_yield_none_fcf():
    assert compute_fcf_yield(None, Decimal("10000000")) is None


def test_fcf_yield_none_market_cap():
    assert compute_fcf_yield(Decimal("1000000"), None) is None


def test_fcf_yield_zero_market_cap_none():
    assert compute_fcf_yield(Decimal("1000000"), Decimal("0")) is None


# ---- GROWTH: full coverage, all higher_better ----

def test_growth_full_coverage():
    percentiles = {"revenue_growth": Decimal("80"), "eps_growth": Decimal("60"), "roce": Decimal("90")}
    assert calculate_growth_score(percentiles) == Decimal("74")


def test_growth_missing_metric_renormalizes():
    percentiles = {"revenue_growth": Decimal("90"), "roce": Decimal("50")}
    result = calculate_growth_score(percentiles)
    expected = (Decimal("40") / Decimal("60")) * Decimal("90") + (Decimal("20") / Decimal("60")) * Decimal("50")
    assert result == expected


def test_growth_exactly_60_coverage_scores_not_insufficient():
    percentiles = {"revenue_growth": Decimal("100"), "roce": Decimal("100")}
    result = calculate_growth_score(percentiles)
    assert result != INSUFFICIENT_DATA
    assert result == Decimal("100")


def test_growth_below_60_coverage_insufficient():
    percentiles = {"roce": Decimal("95")}
    assert calculate_growth_score(percentiles) == INSUFFICIENT_DATA


def test_growth_no_metrics_insufficient():
    assert calculate_growth_score({}) == INSUFFICIENT_DATA


def test_growth_null_treated_same_as_absent_key():
    percentiles = {"revenue_growth": Decimal("90"), "eps_growth": None, "roce": Decimal("50")}
    result_with_none = calculate_growth_score(percentiles)
    result_without_key = calculate_growth_score({"revenue_growth": Decimal("90"), "roce": Decimal("50")})
    assert result_with_none == result_without_key


# ---- VALUE: mixed directions, pb_ratio always missing ----

def test_value_directionality_lower_better_inverts_percentile():
    percentiles = {"pe_ratio": Decimal("90"), "fcf_yield": Decimal("50")}
    expected = (Decimal("40") / Decimal("70")) * Decimal("10") + (Decimal("30") / Decimal("70")) * Decimal("50")
    assert calculate_value_score(percentiles) == expected


def test_value_pb_always_missing_renormalizes_to_pe_and_fcf():
    percentiles = {"pe_ratio": Decimal("20"), "fcf_yield": Decimal("80")}
    result = calculate_value_score(percentiles)
    assert result != INSUFFICIENT_DATA
    expected = (Decimal("40") / Decimal("70")) * (Decimal("100") - Decimal("20")) + (Decimal("30") / Decimal("70")) * Decimal("80")
    assert result == expected


def test_value_only_fcf_available_below_60_insufficient():
    percentiles = {"fcf_yield": Decimal("70")}
    assert calculate_value_score(percentiles) == INSUFFICIENT_DATA


def test_value_only_pe_available_below_60_insufficient():
    percentiles = {"pe_ratio": Decimal("30")}
    assert calculate_value_score(percentiles) == INSUFFICIENT_DATA


def test_value_full_coverage_would_include_pb_if_ever_provided():
    percentiles = {"pe_ratio": Decimal("50"), "pb_ratio": Decimal("50"), "fcf_yield": Decimal("50")}
    assert calculate_value_score(percentiles) == Decimal("50")


# ---- STABILITY: mixed directions, earnings_volatility deferred/missing ----

def test_stability_directionality_lower_better_debt_to_equity():
    percentiles = {"debt_to_equity": Decimal("20"), "roe": Decimal("60")}
    expected = (Decimal("40") / Decimal("70")) * Decimal("80") + (Decimal("30") / Decimal("70")) * Decimal("60")
    assert calculate_stability_score(percentiles) == expected


def test_stability_de_and_roe_only_renormalizes_at_70_coverage():
    percentiles = {"debt_to_equity": Decimal("50"), "roe": Decimal("50")}
    result = calculate_stability_score(percentiles)
    assert result != INSUFFICIENT_DATA
    assert result == Decimal("50")


def test_stability_only_roe_available_below_60_insufficient():
    percentiles = {"roe": Decimal("40")}
    assert calculate_stability_score(percentiles) == INSUFFICIENT_DATA


def test_stability_only_debt_to_equity_available_exactly_40_insufficient():
    percentiles = {"debt_to_equity": Decimal("10")}
    assert calculate_stability_score(percentiles) == INSUFFICIENT_DATA


def test_stability_all_three_would_score_if_volatility_ever_provided():
    percentiles = {"debt_to_equity": Decimal("30"), "roe": Decimal("70"), "earnings_volatility": Decimal("20")}
    result = calculate_stability_score(percentiles)
    expected = (
        Decimal("0.4") * (Decimal("100") - Decimal("30"))
        + Decimal("0.3") * Decimal("70")
        + Decimal("0.3") * (Decimal("100") - Decimal("20"))
    )
    assert result == expected


# ---- Bounds validation: out-of-range percentile is a contract error ----

def test_growth_percentile_above_100_raises_valueerror():
    with pytest.raises(ValueError):
        calculate_growth_score({"revenue_growth": Decimal("150")})


def test_growth_percentile_negative_raises_valueerror():
    with pytest.raises(ValueError):
        calculate_growth_score({"roce": Decimal("-20")})


def test_value_percentile_out_of_range_raises_valueerror():
    with pytest.raises(ValueError):
        calculate_value_score({"pe_ratio": Decimal("101")})


def test_stability_percentile_out_of_range_raises_valueerror():
    with pytest.raises(ValueError):
        calculate_stability_score({"roe": Decimal("100.01")})


def test_percentile_exactly_0_and_100_are_valid_not_errors():
    """Boundary values themselves must NOT raise — only strictly outside
    [0, 100] is invalid."""
    assert calculate_growth_score({"roce": Decimal("0")}) == INSUFFICIENT_DATA  # below 60% coverage, but no error
    assert calculate_growth_score({"revenue_growth": Decimal("100"), "eps_growth": Decimal("100"), "roce": Decimal("0")}) == Decimal("80")
