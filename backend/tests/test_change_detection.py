from datetime import datetime, timezone
from decimal import Decimal

from app.services.change_detection import detect_change, detect_price_move

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)


def test_first_observation_no_event():
    result = detect_change("iid-1", None, Decimal("100"), NOW)
    assert result is None


def test_zero_previous_price_no_event():
    # defensive: avoid div-by-zero, treat as no baseline
    result = detect_change("iid-1", Decimal("0"), Decimal("100"), NOW)
    assert result is None


def test_plus_0_5_pct_no_event():
    result = detect_change("iid-1", Decimal("100"), Decimal("100.5"), NOW)
    assert result is None


def test_plus_1_9_pct_no_event():
    result = detect_change("iid-1", Decimal("100"), Decimal("101.9"), NOW)
    assert result is None


def test_plus_2_0_pct_fires_event():
    result = detect_change("iid-1", Decimal("100"), Decimal("102.0"), NOW)
    assert result is not None
    assert result.event_type == "PRICE_MOVE"
    assert result.delta == Decimal("2.0")


def test_plus_5_pct_fires_event():
    result = detect_change("iid-1", Decimal("100"), Decimal("105"), NOW)
    assert result is not None
    assert result.delta == Decimal("5.0")


def test_minus_2_0_pct_fires_event():
    result = detect_change("iid-1", Decimal("100"), Decimal("98.0"), NOW)
    assert result is not None
    assert result.delta == Decimal("-2.0")
    assert "down" in result.reason


def test_minus_1_9_pct_no_event():
    result = detect_change("iid-1", Decimal("100"), Decimal("98.1"), NOW)
    assert result is None


def test_event_carries_correct_previous_and_current():
    result = detect_price_move("iid-1", Decimal("1300"), Decimal("1404"), NOW)
    assert result.previous_value == Decimal("1300")
    assert result.current_value == Decimal("1404")


def test_instrument_id_propagates():
    result = detect_price_move("some-uuid-string", Decimal("100"), Decimal("110"), NOW)
    assert result.instrument_id == "some-uuid-string"
