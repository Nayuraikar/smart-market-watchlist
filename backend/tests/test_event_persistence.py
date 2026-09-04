from datetime import datetime, timezone
from decimal import Decimal

from app.schemas.change_event import ChangeEvent
from app.services.event_persistence import (
    change_event_to_market_event,
    derive_event_severity,
)

T = datetime(2026, 9, 5, 10, 0, tzinfo=timezone.utc)


def _price_move_event(delta=Decimal("2.5")):
    return ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="PRICE_MOVE",
        previous_value=Decimal("100.00"),
        current_value=Decimal("102.50"),
        delta=delta,
        detected_at=T,
        baseline_timestamp=T,
        reason="price_moved_up_2.5pct",
        details={"previous_price": "100.00", "current_price": "102.50",
                 "pct_change": str(delta), "threshold_pct": "2.0"},
    )


def test_canonical_fields_land_in_details_as_strings():
    ev = _price_move_event()
    row = change_event_to_market_event(ev, ticker="TCS", data_quality="FRESH", source="yfinance")
    assert row.details["previous_value"] == "100.00"
    assert row.details["current_value"] == "102.50"
    assert row.details["delta"] == "2.5"
    assert row.details["reason"] == "price_moved_up_2.5pct"
    assert row.details["baseline_timestamp"] == T.isoformat()
    # event-specific fields preserved alongside canonical ones
    assert row.details["threshold_pct"] == "2.0"


def test_canonical_fields_win_on_collision():
    ev = _price_move_event()
    ev.details["delta"] = "SOMETHING_ELSE"  # simulate an accidental collision
    row = change_event_to_market_event(ev, ticker="TCS", data_quality="FRESH", source="yfinance")
    assert row.details["delta"] == "2.5"  # canonical wins, not the collided value


def test_no_decimal_or_datetime_leaks_into_details():
    ev = _price_move_event()
    row = change_event_to_market_event(ev, ticker="TCS", data_quality="FRESH", source="yfinance")
    for v in row.details.values():
        assert not isinstance(v, Decimal)
        assert not isinstance(v, datetime)


def test_null_baseline_timestamp_serializes_to_none():
    ev = _price_move_event()
    ev.baseline_timestamp = None
    row = change_event_to_market_event(ev, ticker="TCS", data_quality="FRESH", source="yfinance")
    assert row.details["baseline_timestamp"] is None


def test_severity_uses_magnitude_only_small_move_is_medium():
    # PRICE_MOVE threshold is 2.0; a 2.5pct move sits at the 0.5 floor, not HIGH
    ev = _price_move_event(delta=Decimal("2.5"))
    assert derive_event_severity(ev) == "MEDIUM"


def test_severity_large_move_is_high():
    # 3x threshold (6.0pct on a 2.0 threshold) hits the magnitude ceiling
    ev = _price_move_event(delta=Decimal("6.0"))
    assert derive_event_severity(ev) == "HIGH"


def test_severity_defaults_low_for_not_yet_scoreable_type():
    ev = ChangeEvent(
        instrument_id="11111111-1111-1111-1111-111111111111",
        event_type="EARNINGS",
        current_value=Decimal("1.0"),
        delta=Decimal("0"),
        detected_at=T,
        reason="earnings_reported",
        details={},
    )
    assert derive_event_severity(ev) == "LOW"


def test_importance_is_not_copied_from_change_event_importance():
    # ChangeEvent.importance defaults to LOW and must be ignored entirely —
    # MarketEvent.importance comes from derive_event_severity(), not this field
    ev = _price_move_event(delta=Decimal("6.0"))
    assert ev.importance == "LOW"  # the (meaningless) default
    row = change_event_to_market_event(ev, ticker="TCS", data_quality="FRESH", source="yfinance")
    assert row.importance == "HIGH"  # derived from magnitude instead
