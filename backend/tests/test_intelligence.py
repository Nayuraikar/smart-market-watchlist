from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.schemas.change_event import ChangeEvent
from app.services.intelligence import (
    NotScoreable,
    compute_composite_score,
    compute_magnitude,
    get_attention_tier,
    get_data_confidence,
    get_relevance,
    score_event,
    select_top_event,
)

NOW = datetime(2026, 9, 5, tzinfo=timezone.utc)


def _event(event_type: str, delta: Decimal, details: dict | None = None) -> ChangeEvent:
    return ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type=event_type,
        current_value=Decimal("100"),
        delta=delta,
        detected_at=NOW,
        reason="test",
        details=details or {},
    )


# ---- relevance ----

def test_price_move_relevance_direction_dependent_for_stability_only():
    up = _event("PRICE_MOVE", Decimal("3.0"))
    down = _event("PRICE_MOVE", Decimal("-3.0"))
    assert get_relevance(up, "GROWTH") == "MEDIUM"
    assert get_relevance(up, "VALUE") == "MEDIUM"
    assert get_relevance(up, "STABILITY") == "MEDIUM"
    assert get_relevance(down, "GROWTH") == "MEDIUM"
    assert get_relevance(down, "VALUE") == "MEDIUM"
    assert get_relevance(down, "STABILITY") == "HIGH"


def test_base_matrix_relevance_lookup():
    e = _event("VOLUME_SURGE", Decimal("2.5"))
    assert get_relevance(e, "GROWTH") == "HIGH"
    assert get_relevance(e, "VALUE") == "LOW"
    assert get_relevance(e, "STABILITY") == "MEDIUM"


def test_fundamental_change_requires_metric_family():
    e = _event("FUNDAMENTAL_CHANGE", Decimal("1.0"), details={"metric": "roce"})
    with pytest.raises(ValueError):
        get_relevance(e, "GROWTH")


def test_fundamental_change_relevance_by_metric_family():
    e = _event("FUNDAMENTAL_CHANGE", Decimal("1.0"),
               details={"metric": "roce", "metric_family": "growth"})
    assert get_relevance(e, "GROWTH") == "HIGH"
    assert get_relevance(e, "VALUE") == "LOW"
    assert get_relevance(e, "STABILITY") == "LOW"


def test_corporate_action_structural_not_scoreable():
    e = _event("CORPORATE_ACTION", Decimal("0"),
               details={"economic_effect": "structural", "action_type": "merger"})
    with pytest.raises(NotScoreable):
        get_relevance(e, "GROWTH")


def test_corporate_action_missing_action_type_raises():
    e = _event("CORPORATE_ACTION", Decimal("0"),
               details={"economic_effect": "cosmetic"})
    with pytest.raises(ValueError):
        get_relevance(e, "GROWTH")


def test_earnings_not_yet_scoreable_for_magnitude():
    e = _event("EARNINGS", Decimal("1.0"))
    # relevance row exists (section 2)...
    assert get_relevance(e, "GROWTH") == "HIGH"
    # ...but no magnitude curve yet (section 3a)
    with pytest.raises(NotScoreable):
        compute_magnitude(e)


# ---- magnitude ----

def test_magnitude_at_exact_threshold_is_floor():
    e = _event("PRICE_MOVE", Decimal("2.0"))  # exactly PRICE_MOVE_THRESHOLD_PCT
    assert compute_magnitude(e) == Decimal("0.5")


def test_magnitude_at_3x_threshold_is_ceiling():
    e = _event("PRICE_MOVE", Decimal("6.0"))  # 3x threshold
    assert compute_magnitude(e) == Decimal("1.0")


def test_magnitude_beyond_ceiling_clamps():
    e = _event("PRICE_MOVE", Decimal("50.0"))
    assert compute_magnitude(e) == Decimal("1.0")


def test_magnitude_uses_abs_delta_for_price_move():
    up = _event("PRICE_MOVE", Decimal("6.0"))
    down = _event("PRICE_MOVE", Decimal("-6.0"))
    assert compute_magnitude(up) == compute_magnitude(down) == Decimal("1.0")


def test_52w_high_categorical_full_vs_partial_window():
    full = _event("52W_HIGH", Decimal("10"), details={"is_full_window": True})
    partial = _event("52W_HIGH", Decimal("10"), details={"is_full_window": False})
    assert compute_magnitude(full) == Decimal("1.0")
    assert compute_magnitude(partial) == Decimal("0.7")


def test_52w_missing_is_full_window_raises():
    e = _event("52W_LOW", Decimal("-10"), details={})
    with pytest.raises(ValueError):
        compute_magnitude(e)


# ---- confidence / suppression ----

def test_data_confidence_mapping():
    assert get_data_confidence("FRESH") == Decimal("1.0")
    assert get_data_confidence("STALE") == Decimal("0.5")
    assert get_data_confidence("UNAVAILABLE") == Decimal("0.0")


def test_unavailable_event_is_suppressed_not_scored():
    e = _event("PRICE_MOVE", Decimal("6.0"))
    assert score_event(e, "GROWTH", "UNAVAILABLE") is None


# ---- composite score / tier boundaries ----

def test_composite_score_formula():
    score = compute_composite_score(Decimal("0.7"), "MEDIUM", Decimal("1.0"))
    assert score == Decimal("0.7") * Decimal("0.6") * Decimal("1.0")


def test_tier_boundaries_are_inclusive_at_floor():
    assert get_attention_tier(Decimal("0.60")) == "HIGH"
    assert get_attention_tier(Decimal("0.5999")) == "MEDIUM"
    assert get_attention_tier(Decimal("0.30")) == "MEDIUM"
    assert get_attention_tier(Decimal("0.2999")) == "LOW"


def test_low_relevance_can_never_reach_high_tier():
    # max possible: magnitude=1.0, relevance=LOW(0.3), confidence=1.0 -> 0.30, still MEDIUM's floor not HIGH
    score = compute_composite_score(Decimal("1.0"), "LOW", Decimal("1.0"))
    assert get_attention_tier(score) != "HIGH"


def test_stale_event_can_never_reach_high_tier():
    # max possible under STALE: magnitude=1.0, relevance=HIGH(1.0), confidence=0.5 -> 0.50
    score = compute_composite_score(Decimal("1.0"), "HIGH", Decimal("0.5"))
    assert get_attention_tier(score) != "HIGH"
    assert score == Decimal("0.50")


# ---- score_event end-to-end ----

def test_score_event_end_to_end():
    e = _event("PRICE_MOVE", Decimal("-6.0"))  # downward, max magnitude
    scored = score_event(e, "STABILITY", "FRESH")
    assert scored is not None
    assert scored.relevance == "HIGH"
    assert scored.magnitude_normalized == Decimal("1.0")
    assert scored.composite_score == Decimal("1.0") * Decimal("1.0") * Decimal("1.0")
    assert scored.attention_tier == "HIGH"


# ---- top-event tie-break (section 5/5a/5b) ----

def test_select_top_event_max_not_sum():
    price_move = _event("PRICE_MOVE", Decimal("-6.0"))  # STABILITY: HIGH relevance, max magnitude
    volume_surge = _event("VOLUME_SURGE", Decimal("2.0"))  # STABILITY: MEDIUM relevance, floor magnitude
    scored_price = score_event(price_move, "STABILITY", "FRESH")
    scored_volume = score_event(volume_surge, "STABILITY", "FRESH")
    top = select_top_event([scored_price, scored_volume])
    assert top is scored_price
    assert top.composite_score <= Decimal("1.0")  # never boosted past 1.0 by co-firing


def test_select_top_event_tie_break_by_priority():
    # Equal composite_score, equal relevance/magnitude inputs -> EVENT_TYPE_PRIORITY decides.
    # 52W_HIGH (priority 0) must beat PRICE_MOVE (priority 7) at an identical score.
    high_52w = _event("52W_HIGH", Decimal("10"), details={"is_full_window": False})  # magnitude 0.7
    price_move = _event("PRICE_MOVE", Decimal("4.0"))  # magnitude: 0.5 + 0.5*(4-2)/4 = 0.75... not equal by default

    # Force an exact tie explicitly rather than relying on coincidence:
    scored_52w = score_event(high_52w, "GROWTH", "FRESH")   # GROWTH relevance HIGH, magnitude 0.7 -> 0.7
    scored_price = score_event(price_move, "GROWTH", "FRESH")  # GROWTH relevance MEDIUM(0.6)

    # Manually construct a genuine tie via the internal fields to test the tie-break in isolation.
    from app.services.intelligence import ScoredEvent
    tied_price = ScoredEvent(
        event=price_move, relevance="MEDIUM",
        magnitude_normalized=Decimal("0.7") * Decimal("1.0") / Decimal("0.6"),  # irrelevant, only score matters below
        data_confidence=Decimal("1.0"), composite_score=scored_52w.composite_score,
        attention_tier=scored_52w.attention_tier,
    )
    top = select_top_event([scored_52w, tied_price])
    assert top is scored_52w  # 52W_HIGH (priority 0) wins over PRICE_MOVE (priority 7) at equal score


def test_select_top_event_empty_list_returns_none():
    assert select_top_event([]) is None
