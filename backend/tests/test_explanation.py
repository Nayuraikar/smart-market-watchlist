from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.change_event import ChangeEvent
from app.services.explanation import build_explanation
from app.services.intelligence import score_event

T = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def _price_move_event(delta=Decimal("6.0")):
    return ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="PRICE_MOVE",
        previous_value=Decimal("100.00"),
        current_value=Decimal("106.00"),
        delta=delta,
        detected_at=T,
        reason="price_moved_up_6.0pct",
        details={"previous_price": "100.00", "current_price": "106.00",
                 "pct_change": str(delta), "threshold_pct": "2.0"},
    )


def test_price_move_up_growth_fields():
    event = _price_move_event(delta=Decimal("6.0"))
    scored = score_event(event, "GROWTH", "FRESH")
    explanation = build_explanation(scored, "GROWTH")

    assert explanation.what_happened == "Price moved up 6.0%."
    assert explanation.magnitude == "+6.0% price change"
    assert explanation.benchmark_comparison is None
    assert "momentum" in explanation.objective_relevance
    assert explanation.data_status.state == "FRESH"
    assert explanation.data_status.message is None
    assert explanation.attention_tier == scored.attention_tier
    assert explanation.composite_score == scored.composite_score


def test_price_move_down_stability_is_high_relevance_language():
    event = _price_move_event(delta=Decimal("-6.0"))
    scored = score_event(event, "STABILITY", "FRESH")
    explanation = build_explanation(scored, "STABILITY")

    assert explanation.what_happened == "Price moved down 6.0%."
    assert explanation.magnitude == "-6.0% price change"
    assert "highly relevant" in explanation.objective_relevance


def test_stale_data_quality_produces_disclosure_message():
    event = _price_move_event(delta=Decimal("6.0"))
    scored = score_event(event, "GROWTH", "STALE")
    explanation = build_explanation(scored, "GROWTH")

    assert explanation.data_status.state == "STALE"
    assert explanation.data_status.message is not None
    assert "last known price" in explanation.data_status.message
    # never exposed as a percentage/number in the message text
    assert "0.5" not in explanation.data_status.message
    assert "50%" not in explanation.data_status.message


def test_relative_outperformance_has_benchmark_comparison():
    event = ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="RELATIVE_OUTPERFORMANCE",
        previous_value=Decimal("100.00"),
        current_value=Decimal("108.00"),
        delta=Decimal("5.0"),
        detected_at=T,
        reason="relative_outperform_5.0pp",
        details={"stock_return_pct": "8.0", "benchmark_return_pct": "3.0",
                 "relative_performance_pp": "5.0", "threshold_pct": "3.0"},
    )
    scored = score_event(event, "GROWTH", "FRESH")
    explanation = build_explanation(scored, "GROWTH")

    assert "outperformed" in explanation.what_happened
    assert explanation.benchmark_comparison is not None
    assert "8.0%" in explanation.benchmark_comparison
    assert "3.0%" in explanation.benchmark_comparison


def test_volume_surge_fields():
    event = ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="VOLUME_SURGE",
        current_value=Decimal("500000"),
        delta=Decimal("2.5"),
        detected_at=T,
        reason="volume_surge_2.5x_average",
        details={"current_volume": "500000", "avg_volume_20d": "200000",
                 "ratio": "2.5", "pct_above_average": "150.0",
                 "window": "20", "threshold": "2.0"},
    )
    scored = score_event(event, "GROWTH", "FRESH")
    explanation = build_explanation(scored, "GROWTH")

    assert explanation.what_happened == "Trading volume surged to 2.5x its 20-day average."
    assert explanation.magnitude == "2.5x average volume"
    assert explanation.benchmark_comparison is None


def test_52w_high_full_window_uses_52_week_label():
    event = ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="52W_HIGH",
        previous_value=Decimal("150.00"),
        current_value=Decimal("160.00"),
        delta=Decimal("10.00"),
        detected_at=T,
        reason="new_high_252d_window",
        details={"prior_max": "150.00", "window_days_used": 252,
                 "window_target_days": 252, "is_full_window": True},
    )
    scored = score_event(event, "VALUE", "FRESH")
    explanation = build_explanation(scored, "VALUE")

    assert "52-week" in explanation.what_happened
    assert "moderately relevant" in explanation.objective_relevance


def test_52w_low_partial_window_uses_day_count_label():
    event = ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="52W_LOW",
        previous_value=Decimal("100.00"),
        current_value=Decimal("90.00"),
        delta=Decimal("-10.00"),
        detected_at=T,
        reason="new_low_10d_window",
        details={"prior_min": "100.00", "window_days_used": 10,
                 "window_target_days": 252, "is_full_window": False},
    )
    scored = score_event(event, "STABILITY", "FRESH")
    explanation = build_explanation(scored, "STABILITY")

    assert "10-day" in explanation.what_happened
    assert "highly relevant" in explanation.objective_relevance
