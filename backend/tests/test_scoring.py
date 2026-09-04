from decimal import Decimal

from app.services.scoring import (
    compute_percentile_rank, compute_fcf_yield,
    calculate_growth_score, calculate_value_score, calculate_stability_score,
    INSUFFICIENT_DATA,
)


# ---- compute_percentile_rank: generic, no financial semantics ----

def test_percentile_rank_basic_no_ties():
    population = [Decimal("10"), Decimal("20"), Decimal("30"), Decimal("40"), Decimal("50")]
    # value 30 -> 2 below, 1 equal, n=5 -> (2 + 0.5)/5*100 = 50
    assert compute_percentile_rank(Decimal("30"), population) == Decimal("50")


def test_percentile_rank_highest_value():
    population = [Decimal("10"), Decimal("20"), Decimal("30")]
    # 4 below (itself included as "below" count excludes self via < comparison)
    # below=2 (10,20 < 30... wait 30 is being ranked against its own population)
    result = compute_percentile_rank(Decimal("30"), population)
    assert result == Decimal("83.33333333333333333333333333")  # (2 + 0.5)/3*100


def test_percentile_rank_lowest_value():
    population = [Decimal("10"), Decimal("20"), Decimal("30")]
    result = compute_percentile_rank(Decimal("10"), population)
    assert result == Decimal("16.66666666666666666666666667")  # (0 + 0.5)/3*100


def test_percentile_rank_ties_get_midpoint():
    """Three-way tie: value appears 3 times in a 5-element population.
    below=0, equal=3 -> (0 + 1.5)/5*100 = 30 for each tied member."""
    population = [Decimal("50"), Decimal("50"), Decimal("50"), Decimal("60"), Decimal("70")]
    assert compute_percentile_rank(Decimal("50"), population) == Decimal("30")


def test_percentile_rank_singleton_population_is_50():
    """A population of exactly one element equal to the value ranks at
    the midpoint, 50 — neither definitionally highest nor lowest."""
    assert compute_percentile_rank(Decimal("100"), [Decimal("100")]) == Decimal("50")


def test_percentile_rank_empty_population_none():
    assert compute_percentile_rank(Decimal("100"), []) is None


# ---- compute_fcf_yield: derived cross-table metric ----

def test_fcf_yield_basic():
    assert compute_fcf_yield(Decimal("1000000"), Decimal("10000000")) == Decimal("0.1")


def test_fcf_yield_none_fcf():
    assert compute_fcf_yield(None, Decimal("10000000")) is None


def test_fcf_yield_none_market_cap():
    assert compute_fcf_yield(Decimal("1000000"), None) is None


def test_fcf_yield_zero_market_cap_none():
    assert compute_fcf_yield(Decimal("1000000"), Decimal("0")) is None


# ---- GROWTH: full coverage, all higher_better ----

def test_growth_full_coverage():
    percentiles = {"revenue_growth": Decimal("80"), "eps_growth": Decimal("60"), "roce": Decimal("90")}
    # 0.4*80 + 0.4*60 + 0.2*90 = 32 + 24 + 18 = 74
    assert calculate_growth_score(percentiles) == Decimal("74")


def test_growth_missing_metric_renormalizes():
    """eps_growth missing -> available weight = 40+20 = 60 (exactly the
    coverage floor). Renormalized: revenue_growth weight becomes 40/60,
    roce becomes 20/60."""
    percentiles = {"revenue_growth": Decimal("90"), "roce": Decimal("50")}
    result = calculate_growth_score(percentiles)
    expected = (Decimal("40") / Decimal("60")) * Decimal("90") + (Decimal("20") / Decimal("60")) * Decimal("50")
    assert result == expected


def test_growth_exactly_60_coverage_scores_not_insufficient():
    """Same case as above, phrased as the explicit exactly-60% test:
    coverage == 60 must NOT be treated as below-threshold."""
    percentiles = {"revenue_growth": Decimal("100"), "roce": Decimal("100")}
    result = calculate_growth_score(percentiles)
    assert result != INSUFFICIENT_DATA
    assert result == Decimal("100")


def test_growth_below_60_coverage_insufficient():
    """Only roce present -> available weight = 20, below 60 -> INSUFFICIENT_DATA."""
    percentiles = {"roce": Decimal("95")}
    assert calculate_growth_score(percentiles) == INSUFFICIENT_DATA


def test_growth_no_metrics_insufficient():
    assert calculate_growth_score({}) == INSUFFICIENT_DATA


def test_growth_null_population_values_excluded_upstream():
    """Confirms this layer treats an explicit None the same as an absent
    key — the null-exclusion from the population happens one layer up
    (at percentile computation time), not here."""
    percentiles = {"revenue_growth": Decimal("90"), "eps_growth": None, "roce": Decimal("50")}
    result_with_none = calculate_growth_score(percentiles)
    result_without_key = calculate_growth_score({"revenue_growth": Decimal("90"), "roce": Decimal("50")})
    assert result_with_none == result_without_key


# ---- VALUE: mixed directions, pb_ratio always missing ----

def test_value_directionality_lower_better_inverts_percentile():
    """pe_ratio at the 90th raw percentile (i.e. among the highest P/E
    values in the universe) should score LOW, not high, since lower P/E
    is better. Direction inversion: 100 - 90 = 10."""
    percentiles = {"pe_ratio": Decimal("90"), "fcf_yield": Decimal("50")}
    # pe weight 40, fcf weight 30 -> available = 70 (>=60, passes)
    # pe contributes (100-90)=10 directionally, fcf contributes 50 directly
    expected = (Decimal("40") / Decimal("70")) * Decimal("10") + (Decimal("30") / Decimal("70")) * Decimal("50")
    assert calculate_value_score(percentiles) == expected


def test_value_pb_always_missing_renormalizes_to_pe_and_fcf():
    """pb_ratio omitted entirely (as it always will be per DECISIONS.md)
    -> available weight = 40 (pe) + 30 (fcf) = 70, above the 60 floor."""
    percentiles = {"pe_ratio": Decimal("20"), "fcf_yield": Decimal("80")}
    result = calculate_value_score(percentiles)
    assert result != INSUFFICIENT_DATA
    expected = (Decimal("40") / Decimal("70")) * (Decimal("100") - Decimal("20")) + (Decimal("30") / Decimal("70")) * Decimal("80")
    assert result == expected


def test_value_only_fcf_available_below_60_insufficient():
    """Only fcf_yield (weight 30) available -> below 60 -> INSUFFICIENT_DATA."""
    percentiles = {"fcf_yield": Decimal("70")}
    assert calculate_value_score(percentiles) == INSUFFICIENT_DATA


def test_value_only_pe_available_below_60_insufficient():
    """Only pe_ratio (weight 40) available -> below 60 -> INSUFFICIENT_DATA."""
    percentiles = {"pe_ratio": Decimal("30")}
    assert calculate_value_score(percentiles) == INSUFFICIENT_DATA


def test_value_full_coverage_would_include_pb_if_ever_provided():
    """Documents that the function itself does not hardcode pb_ratio's
    absence — if a caller ever did supply it, it would be scored
    normally. The 'always missing' behavior lives in the caller/data
    layer (DECISIONS.md), not in calculate_value_score's logic."""
    percentiles = {"pe_ratio": Decimal("50"), "pb_ratio": Decimal("50"), "fcf_yield": Decimal("50")}
    assert calculate_value_score(percentiles) == Decimal("50")


# ---- STABILITY: mixed directions, earnings_volatility deferred/missing ----

def test_stability_directionality_lower_better_debt_to_equity():
    """debt_to_equity at the 20th raw percentile (low D/E, good) should
    score HIGH: 100 - 20 = 80."""
    percentiles = {"debt_to_equity": Decimal("20"), "roe": Decimal("60")}
    expected = (Decimal("40") / Decimal("70")) * Decimal("80") + (Decimal("30") / Decimal("70")) * Decimal("60")
    assert calculate_stability_score(percentiles) == expected


def test_stability_de_and_roe_only_renormalizes_at_70_coverage():
    """The exact case from DECISIONS.md: earnings_volatility deferred and
    always missing, D/E + ROE = 70% coverage, above the 60 floor, scores
    normally without the frozen weights changing."""
    percentiles = {"debt_to_equity": Decimal("50"), "roe": Decimal("50")}
    result = calculate_stability_score(percentiles)
    assert result != INSUFFICIENT_DATA
    assert result == Decimal("50")  # both directional percentiles are 50 regardless of direction


def test_stability_only_roe_available_below_60_insufficient():
    """Only roe (weight 30) available -> below 60 -> INSUFFICIENT_DATA."""
    percentiles = {"roe": Decimal("40")}
    assert calculate_stability_score(percentiles) == INSUFFICIENT_DATA


def test_stability_only_debt_to_equity_available_exactly_40_insufficient():
    """Only debt_to_equity (weight 40) available -> below 60 -> INSUFFICIENT_DATA.
    Confirms 40 alone, despite being the largest single metric, still
    doesn't clear the floor on its own."""
    percentiles = {"debt_to_equity": Decimal("10")}
    assert calculate_stability_score(percentiles) == INSUFFICIENT_DATA


def test_stability_all_three_would_score_if_volatility_ever_provided():
    """Same documentation purpose as the VALUE equivalent above: the
    'always missing' behavior for earnings_volatility lives outside this
    function, not hardcoded into it."""
    percentiles = {"debt_to_equity": Decimal("30"), "roe": Decimal("70"), "earnings_volatility": Decimal("20")}
    result = calculate_stability_score(percentiles)
    expected = (
        Decimal("0.4") * (Decimal("100") - Decimal("30"))
        + Decimal("0.3") * Decimal("70")
        + Decimal("0.3") * (Decimal("100") - Decimal("20"))
    )
    assert result == expected
