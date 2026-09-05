import json
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from app.services.change_detection import (
    detect_change, detect_price_move, detect_relative_outperformance,
    compute_return, compute_relative_performance,
)

NOW = datetime(2026, 9, 5, 12, 0, 0, tzinfo=timezone.utc)
FIXTURE_PATH = Path(__file__).parent.parent / "data" / "scenarios" / "phase6_market_history.json"
if not FIXTURE_PATH.exists():
    FIXTURE_PATH = Path(__file__).resolve().parents[2] / "data/scenarios/phase6_market_history.json"


def _load_fixture():
    with open(FIXTURE_PATH) as f:
        return json.load(f)


# ---- PRICE_MOVE boundary tests (unchanged logic, updated for list return) ----

def test_first_observation_no_event():
    assert detect_change("iid-1", None, Decimal("100"), NOW) == []


def test_zero_previous_price_no_event():
    assert detect_change("iid-1", Decimal("0"), Decimal("100"), NOW) == []


def test_plus_0_5_pct_no_event():
    assert detect_change("iid-1", Decimal("100"), Decimal("100.5"), NOW) == []


def test_plus_1_9_pct_no_event():
    assert detect_change("iid-1", Decimal("100"), Decimal("101.9"), NOW) == []


def test_plus_2_0_pct_fires_event():
    events = detect_change("iid-1", Decimal("100"), Decimal("102.0"), NOW)
    assert len(events) == 1
    assert events[0].event_type == "PRICE_MOVE"
    assert events[0].delta == Decimal("2.0")


def test_plus_5_pct_fires_event():
    events = detect_change("iid-1", Decimal("100"), Decimal("105"), NOW)
    assert len(events) == 1
    assert events[0].delta == Decimal("5.0")


def test_minus_2_0_pct_fires_event():
    events = detect_change("iid-1", Decimal("100"), Decimal("98.0"), NOW)
    assert len(events) == 1
    assert events[0].delta == Decimal("-2.0")
    assert "down" in events[0].reason


def test_minus_1_9_pct_no_event():
    assert detect_change("iid-1", Decimal("100"), Decimal("98.1"), NOW) == []


def test_event_carries_correct_previous_and_current():
    result = detect_price_move("iid-1", Decimal("1300"), Decimal("1404"), NOW)
    assert result.previous_value == Decimal("1300")
    assert result.current_value == Decimal("1404")


def test_instrument_id_propagates():
    result = detect_price_move("some-uuid-string", Decimal("100"), Decimal("110"), NOW)
    assert result.instrument_id == "some-uuid-string"


# ---- 6.4: relative performance vs NIFTY 50 ----

def test_compute_return_basic():
    assert compute_return(Decimal("100"), Decimal("105")) == Decimal("5")


def test_compute_return_none_baseline():
    assert compute_return(None, Decimal("100")) is None


def test_compute_return_zero_baseline():
    assert compute_return(Decimal("0"), Decimal("100")) is None


def test_relative_performance_fixture_day1_to_day21():
    """Hand-computed from data/scenarios/phase6_market_history.json:
    RELIANCE 1300->1365 (+5.0%), NIFTY 24000->24240 (+1.0%), relative = +4.0pp."""
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    nifty = data["NIFTY50"]
    relative = compute_relative_performance(
        Decimal(str(reliance[0]["close"])), Decimal(str(reliance[-1]["close"])),
        Decimal(str(nifty[0]["close"])), Decimal(str(nifty[-1]["close"])),
    )
    assert relative == Decimal("4.0")


def test_relative_performance_fixture_day1_to_day11_below_threshold():
    """Hand-computed: RELIANCE 1300->1332.5 (+2.5%), NIFTY 24000->24120 (+0.5%),
    relative = +2.0pp — below the 3.0pp threshold, must NOT fire."""
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    nifty = data["NIFTY50"]
    event = detect_relative_outperformance(
        "iid-reliance",
        Decimal(str(reliance[0]["close"])), Decimal(str(reliance[10]["close"])),
        Decimal(str(nifty[0]["close"])), Decimal(str(nifty[10]["close"])),
        NOW,
    )
    assert event is None


def test_relative_outperformance_fires_at_threshold_fixture():
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    nifty = data["NIFTY50"]
    event = detect_relative_outperformance(
        "iid-reliance",
        Decimal(str(reliance[0]["close"])), Decimal(str(reliance[-1]["close"])),
        Decimal(str(nifty[0]["close"])), Decimal(str(nifty[-1]["close"])),
        NOW,
    )
    assert event is not None
    assert event.event_type == "RELATIVE_OUTPERFORMANCE"
    assert event.delta == Decimal("4.0")
    assert "outperform" in event.reason


def test_relative_underperformance_fires_negative():
    event = detect_relative_outperformance(
        "iid-1", Decimal("100"), Decimal("100.5"),  # stock +0.5%
        Decimal("100"), Decimal("104"),               # benchmark +4.0%
        NOW,
    )
    assert event is not None
    assert event.delta == Decimal("-3.5")
    assert "underperform" in event.reason


def test_relative_performance_missing_benchmark_no_event():
    event = detect_relative_outperformance(
        "iid-1", Decimal("100"), Decimal("110"), None, Decimal("100"), NOW,
    )
    assert event is None


# ---- Regression: coexistence of multiple event types on one observation ----

def test_price_move_and_relative_outperformance_coexist():
    """The specific case that forced detect_change() to return list[ChangeEvent]
    instead of ChangeEvent | None: a single observation legitimately fires
    two different event types at once. Uses fixture day1->day21 values,
    which cross both the 2% PRICE_MOVE threshold and the 3pp
    RELATIVE_OUTPERFORMANCE threshold simultaneously."""
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    nifty = data["NIFTY50"]

    events = detect_change(
        "iid-reliance",
        Decimal(str(reliance[0]["close"])), Decimal(str(reliance[-1]["close"])),
        NOW,
        benchmark_previous=Decimal(str(nifty[0]["close"])),
        benchmark_current=Decimal(str(nifty[-1]["close"])),
    )

    event_types = {e.event_type for e in events}
    assert event_types == {"PRICE_MOVE", "RELATIVE_OUTPERFORMANCE"}
    assert len(events) == 2


def test_detect_change_without_benchmark_only_checks_price():
    """benchmark_current omitted -> no RELATIVE_OUTPERFORMANCE check at all,
    even if it would have fired. Confirms the function doesn't silently
    fabricate a benchmark comparison when none was provided."""
    events = detect_change("iid-1", Decimal("100"), Decimal("110"), NOW)
    assert len(events) == 1
    assert events[0].event_type == "PRICE_MOVE"


def test_detect_change_empty_list_when_nothing_fires():
    events = detect_change("iid-1", Decimal("100"), Decimal("100.1"), NOW)
    assert events == []


# ---- 6.5: relative volume (RVOL) vs 20-day average ----

from app.services.change_detection import detect_volume_surge, compute_average  # noqa: E402


def test_compute_average_basic():
    assert compute_average([Decimal("10"), Decimal("20"), Decimal("30")]) == Decimal("20")


def test_compute_average_empty_list_none():
    assert compute_average([]) is None


def test_volume_surge_fixture_day21():
    """Fixture: 20 days flat at 10,000,000, day 21 at 25,000,000 = 2.5x."""
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    trailing = [Decimal(str(d["volume"])) for d in reliance[0:20]]
    current = Decimal(str(reliance[20]["volume"]))
    event = detect_volume_surge("iid-reliance", current, trailing, NOW)
    assert event is not None
    assert event.event_type == "VOLUME_SURGE"
    assert event.delta == Decimal("2.5")
    assert event.previous_value == Decimal("10000000")


def test_volume_surge_below_threshold_no_event():
    trailing = [Decimal("10000000")] * 20
    event = detect_volume_surge("iid-1", Decimal("15000000"), trailing, NOW)  # 1.5x
    assert event is None


def test_volume_surge_exactly_at_threshold_fires():
    trailing = [Decimal("10000000")] * 20
    event = detect_volume_surge("iid-1", Decimal("20000000"), trailing, NOW)  # exactly 2.0x
    assert event is not None
    assert event.delta == Decimal("2.0")


def test_volume_surge_cold_start_fewer_than_window_no_event():
    """19 days of history is not enough — must not fabricate a partial
    baseline, same rule as detect_price_move's None-previous_price case."""
    trailing = [Decimal("10000000")] * 19
    event = detect_volume_surge("iid-1", Decimal("50000000"), trailing, NOW)
    assert event is None


def test_volume_surge_only_uses_trailing_window_not_extra_history():
    """Regression for the off-by-one bug: pass 25 days of history where
    the OLDEST 5 days are artificially huge. If the function incorrectly
    averaged all 25 instead of the trailing 20, the average would be
    dragged up and this legitimate surge would be masked."""
    old_huge_days = [Decimal("100000000")] * 5   # would wreck the average if included
    correct_window = [Decimal("10000000")] * 20
    trailing = old_huge_days + correct_window
    event = detect_volume_surge("iid-1", Decimal("25000000"), trailing, NOW)
    assert event is not None
    assert event.previous_value == Decimal("10000000")  # proves the huge days were excluded
    assert event.delta == Decimal("2.5")


def test_volume_surge_zero_average_no_event():
    trailing = [Decimal("0")] * 20
    event = detect_volume_surge("iid-1", Decimal("1000"), trailing, NOW)
    assert event is None


def test_detect_change_includes_volume_surge_when_provided():
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    trailing = [Decimal(str(d["volume"])) for d in reliance[0:20]]
    current_vol = Decimal(str(reliance[20]["volume"]))

    events = detect_change(
        "iid-reliance",
        Decimal("1361.75"), Decimal("1365.00"),  # tiny price move, won't fire PRICE_MOVE
        NOW,
        current_volume=current_vol,
        trailing_volumes=trailing,
    )
    event_types = {e.event_type for e in events}
    assert "VOLUME_SURGE" in event_types


def test_detect_change_without_volume_args_skips_volume_check():
    """current_volume/trailing_volumes omitted -> no VOLUME_SURGE check
    at all, even implicitly. Same 'don't fabricate' rule as the
    benchmark-omitted case."""
    events = detect_change("iid-1", Decimal("100"), Decimal("100.1"), NOW)
    assert events == []


def test_all_three_event_types_coexist():
    """Extends the 6.4 coexistence regression: a single observation can
    fire PRICE_MOVE + RELATIVE_OUTPERFORMANCE + VOLUME_SURGE together."""
    data = _load_fixture()
    reliance = data["RELIANCE.NS"]
    nifty = data["NIFTY50"]
    trailing = [Decimal(str(d["volume"])) for d in reliance[0:20]]

    events = detect_change(
        "iid-reliance",
        Decimal(str(reliance[0]["close"])), Decimal(str(reliance[-1]["close"])),
        NOW,
        benchmark_previous=Decimal(str(nifty[0]["close"])),
        benchmark_current=Decimal(str(nifty[-1]["close"])),
        current_volume=Decimal(str(reliance[20]["volume"])),
        trailing_volumes=trailing,
    )
    event_types = {e.event_type for e in events}
    assert event_types == {"PRICE_MOVE", "RELATIVE_OUTPERFORMANCE", "VOLUME_SURGE"}
    assert len(events) == 3


# ---- 6.6: 52W_HIGH / 52W_LOW as state transitions (adaptive window) ----

from app.services.change_detection import detect_52w_high, detect_52w_low  # noqa: E402


def test_52w_high_cold_start_fewer_than_min_observations_no_event():
    """3 prior observations is below the 5-observation floor — must not
    fire, same 'don't fabricate a baseline' rule as the other detectors."""
    trailing = [Decimal("100"), Decimal("105"), Decimal("110")]
    event = detect_52w_high("iid-1", Decimal("200"), trailing, NOW)
    assert event is None


def test_52w_low_cold_start_fewer_than_min_observations_no_event():
    trailing = [Decimal("100"), Decimal("95"), Decimal("90")]
    event = detect_52w_low("iid-1", Decimal("1"), trailing, NOW)
    assert event is None


def test_52w_high_partial_window_fires_and_reports_partial():
    """Exactly 5 prior observations (the floor) — fires, but is_full_window
    must be False and window_days_used must equal 5, not 252."""
    trailing = [Decimal("100"), Decimal("102"), Decimal("101"), Decimal("103"), Decimal("104")]
    event = detect_52w_high("iid-1", Decimal("110"), trailing, NOW)
    assert event is not None
    assert event.event_type == "52W_HIGH"
    assert event.details["window_days_used"] == 5
    assert event.details["window_target_days"] == 252
    assert event.details["is_full_window"] is False
    assert event.previous_value == Decimal("104")


def test_52w_low_partial_window_fires_and_reports_partial():
    trailing = [Decimal("100"), Decimal("98"), Decimal("99"), Decimal("97"), Decimal("96")]
    event = detect_52w_low("iid-1", Decimal("90"), trailing, NOW)
    assert event is not None
    assert event.event_type == "52W_LOW"
    assert event.details["window_days_used"] == 5
    assert event.details["is_full_window"] is False
    assert event.previous_value == Decimal("96")


def test_52w_high_full_window_reports_full():
    """252 prior observations -> is_full_window True, and only the most
    recent 252 are used even if more are passed in."""
    trailing = [Decimal("100")] * 260  # 260 > 252, extra 8 must be ignored
    trailing[-1] = Decimal("150")  # most recent prior obs is the max
    event = detect_52w_high("iid-1", Decimal("200"), trailing, NOW)
    assert event is not None
    assert event.details["window_days_used"] == 252
    assert event.details["is_full_window"] is True
    assert event.previous_value == Decimal("150")


def test_52w_high_not_new_high_no_event():
    trailing = [Decimal("100"), Decimal("200"), Decimal("150"), Decimal("120"), Decimal("110")]
    event = detect_52w_high("iid-1", Decimal("199"), trailing, NOW)  # below prior max of 200
    assert event is None


def test_52w_low_not_new_low_no_event():
    trailing = [Decimal("100"), Decimal("50"), Decimal("70"), Decimal("80"), Decimal("90")]
    event = detect_52w_low("iid-1", Decimal("51"), trailing, NOW)  # above prior min of 50
    assert event is None


def test_52w_high_boundary_equal_to_prior_max_no_event():
    """Exactly equal to the prior max must NOT fire — strict '>' only,
    this is the core of the 'was-below -> now-crosses, not is-equal-to' rule."""
    trailing = [Decimal("100"), Decimal("105"), Decimal("103"), Decimal("101"), Decimal("104")]
    event = detect_52w_high("iid-1", Decimal("105"), trailing, NOW)
    assert event is None


def test_52w_low_boundary_equal_to_prior_min_no_event():
    trailing = [Decimal("100"), Decimal("95"), Decimal("97"), Decimal("99"), Decimal("96")]
    event = detect_52w_low("iid-1", Decimal("95"), trailing, NOW)
    assert event is None


def test_52w_high_plateau_does_not_duplicate_across_two_days():
    """Simulates two consecutive days: day N sets a new high, day N+1
    repeats the exact same price. Day N+1 must NOT fire again, because
    day N's record price has entered day N+1's trailing window and the
    plateau price only ties it rather than beating it."""
    trailing_day_n = [Decimal("100"), Decimal("102"), Decimal("101"), Decimal("103"), Decimal("104")]
    new_high_price = Decimal("110")

    day_n_event = detect_52w_high("iid-1", new_high_price, trailing_day_n, NOW)
    assert day_n_event is not None  # day N: legitimate new high

    trailing_day_n_plus_1 = trailing_day_n + [new_high_price]  # today's record enters tomorrow's window
    day_n_plus_1_event = detect_52w_high("iid-1", new_high_price, trailing_day_n_plus_1, NOW)
    assert day_n_plus_1_event is None  # day N+1: same price, must not re-fire


def test_52w_low_plateau_does_not_duplicate_across_two_days():
    trailing_day_n = [Decimal("100"), Decimal("98"), Decimal("99"), Decimal("97"), Decimal("96")]
    new_low_price = Decimal("90")

    day_n_event = detect_52w_low("iid-1", new_low_price, trailing_day_n, NOW)
    assert day_n_event is not None

    trailing_day_n_plus_1 = trailing_day_n + [new_low_price]
    day_n_plus_1_event = detect_52w_low("iid-1", new_low_price, trailing_day_n_plus_1, NOW)
    assert day_n_plus_1_event is None


def test_detect_change_includes_both_52w_events_when_provided():
    """A single call can only realistically fire one of HIGH/LOW (price
    can't be both above a max and below a min), but confirms detect_change
    wires trailing_prices through to both detectors correctly."""
    trailing = [Decimal("100"), Decimal("105"), Decimal("103"), Decimal("101"), Decimal("104")]
    events = detect_change(
        "iid-1", Decimal("104"), Decimal("106"),  # tiny move, won't fire PRICE_MOVE
        NOW,
        trailing_prices=trailing,
    )
    event_types = {e.event_type for e in events}
    assert "52W_HIGH" in event_types
    assert "52W_LOW" not in event_types


def test_detect_change_without_trailing_prices_skips_52w_check():
    events = detect_change("iid-1", Decimal("100"), Decimal("100.1"), NOW)
    assert events == []
